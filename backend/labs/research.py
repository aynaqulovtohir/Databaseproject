"""Ilmiy tadqiqot uchun laboratoriya ma'lumotlarini anonim eksport qilish.

Natija — ZIP arxiv: urinishlar.csv (har bir ishga tushirish), xulosa.csv (har bir
talaba va laboratoriya bo'yicha), testlar.csv va test_javoblari.csv (kirish/chiqish
testlari) hamda ustunlar tavsifi (README.txt).

Anonimlik: talabaning ismi, logini va SQL kodi eksportga kirmaydi. Talaba o'rniga
doimiy taxallus (masalan, T-1A2B3C4D) yoziladi: u SECRET_KEY dan hosil qilinadi,
shuning uchun har eksportda bir xil bo'ladi, lekin undan talabani aniqlab bo'lmaydi.
"""
import csv
import hashlib
import hmac
import io
import zipfile
from collections import defaultdict

from django.conf import settings
from django.utils import timezone

from users.consent import consent_required, participant_ids, research_participants
from users.models import User

from .checker import ERROR_TIPS
from .models import AIOutputReview, BlindReview, LabAttempt, LabGrade, PeerReview
from .psychometrics import MIN_STUDENTS as MIN_ANALYSIS_STUDENTS

QUIZ_KINDS = {"pre": "kirish", "post": "chiqish", "delayed": "kechiktirilgan", "practice": "oddiy", "survey": "sorovnoma"}
QUESTION_KINDS = {"single": "bitta", "multiple": "kop", "likert": "likert"}
QUIZ_STATUSES = {"submitted": "topshirgan", "in_progress": "boshlagan", "not_started": "boshlamagan"}

QUIZ_COLUMNS = [
    "talaba",
    "guruh",
    "ai_yoqilgan",
    "test_id",
    "test",
    "test_turi",
    "holat",
    "ball",
    "maksimal_ball",
    "foiz",
    "boshlangan",
    "topshirilgan",
    "davomiylik_daqiqa",
]

ANSWER_COLUMNS = [
    "talaba",
    "guruh",
    "test_id",
    "test_turi",
    "savol_raqami",
    "savol_turi",
    "ball",
    "maksimal_ball",
    "togri",
    "javob",
]

REVIEW_COLUMNS = [
    "talaba",
    "guruh",
    "ai_yoqilgan",
    "laboratoriya_id",
    "laboratoriya",
    "laboratoriya_turi",
    "baholovchi",
    "tizim_ball",
    "tizim_manbasi",
    "oqituvchi_ball",
    "farq",
    "tizim_baho",
    "oqituvchi_baho",
    "baholangan",
]

# O'zbekiston va MDH hududidagi Excel CSV faylni nuqtali vergul bilan to'g'ri ochadi
DELIMITER = ";"

# Eski urinishlarda SQLSTATE saqlanmagan: u o'zbekcha tushuntirish matnidan tiklanadi
TIP_TO_SQLSTATE = {tip: code for code, tip in ERROR_TIPS.items()}

ERROR_CATEGORIES = {
    "42601": "sintaksis",
    "42P01": "jadval_topilmadi",
    "42703": "ustun_topilmadi",
    "42P07": "jadval_takrorlandi",
    "42701": "ustun_takrorlandi",
    "42702": "ustun_noaniq",
    "42803": "group_by",
    "42883": "funksiya_yoki_operator",
    "42804": "tur_mos_emas",
    "42704": "tur_topilmadi",
    "42830": "fk_kalitsiz_ustunga",
    "42P16": "jadval_tarifi_xato",
    "42501": "ruxsat_yoq",
    "22P02": "qiymat_turi",
    "22001": "matn_uzun",
    "22003": "son_chegarasi",
    "22012": "nolga_bolish",
    "21000": "ichki_sorov_kop_qator",
    "23502": "not_null_buzildi",
    "23503": "fk_buzildi",
    "23505": "unique_buzildi",
    "23514": "check_buzildi",
    "57014": "vaqt_tugadi",
}

# Namunadan farq matni -> toifa. Birinchi mos kelgani olinadi, shuning uchun aniqrog'i oldinda turadi.
DIFFERENCE_CATEGORIES = [
    # ER-diagramma laboratoriyasi
    ("obyekt yetishmaydi", "er_obyekt_yetishmaydi"),
    ("Ortiqcha obyekt", "er_ortiqcha_obyekt"),
    ("atribut yetishmaydi", "er_atribut_yetishmaydi"),
    ("ortiqcha atribut", "er_ortiqcha_atribut"),
    ("asosiy kalit (PK)", "er_asosiy_kalit"),
    ("oraliq obyekti orqali", "er_mn_oraliq_obyekt"),
    ("kardinalligi noto'g'ri", "er_kardinallik"),
    ("orasida bog'lanish yetishmaydi", "er_boglanish_yetishmaydi"),
    ("ortiqcha bog'lanish", "er_ortiqcha_boglanish"),
    ("Diagramma bo'sh", "er_bosh_diagramma"),
    # SQL laboratoriyasi
    ("PRIMARY KEY cheklovi", "pk_yetishmaydi"),
    ("FOREIGN KEY cheklovi", "fk_yetishmaydi"),
    ("UNIQUE cheklovi", "unique_yetishmaydi"),
    ("CHECK cheklovi", "check_yetishmaydi"),
    ("cheklov cheklovi", "cheklov_yetishmaydi"),
    ("ustunining turi", "ustun_turi"),
    ("NOT NULL bo'lishi kerak", "not_null_yetishmaydi"),
    ("(NULL) qiymatga ruxsat", "ortiqcha_not_null"),
    ("jadvali yo'q", "jadval_yetishmaydi"),
    ("Ortiqcha jadval", "ortiqcha_jadval"),
    ("ustun yetishmaydi", "ustun_yetishmaydi"),
    ("ortiqcha ustun", "ortiqcha_ustun"),
    ("jadvalida qatorlar soni to'g'ri", "jadval_qiymatlari"),
    ("jadvalidagi ma'lumotlar", "jadval_qatorlari_soni"),
    ("natija qaytarmadi", "select_yoq"),
    ("Natijadagi ustunlar soni", "natija_ustunlari_soni"),
    ("Natijadagi qatorlar soni", "natija_qatorlari_soni"),
    ("tartibi kutilganidan", "natija_tartibi"),
    ("ayrim qiymatlar kutilganidan", "natija_qiymatlari"),
]

ATTEMPT_COLUMNS = [
    "talaba",
    "guruh",
    "ai_yoqilgan",
    "laboratoriya_id",
    "laboratoriya",
    "laboratoriya_turi",
    "urinish_raqami",
    "vaqt",
    "birinchi_urinishdan_daqiqa",
    "turi",
    "natija",
    "togri",
    "xato_turlari",
    "ai_maslahat",
    "maslahat_darajasi",
    "kod_qatorlari",
    "kod_belgilari",
    "ishonch",
]

SUMMARY_COLUMNS = [
    "talaba",
    "guruh",
    "ai_yoqilgan",
    "laboratoriya_id",
    "laboratoriya",
    "laboratoriya_turi",
    "urinishlar",
    "yechildi",
    "togri_gacha_urinishlar",
    "yechish_vaqti_daqiqa",
    "baza_xatolari",
    "natija_farqlari",
    "ai_maslahatlar",
    "maslahat_darajalari_jami",
    "eng_yuqori_maslahat_darajasi",
    "maslahatdan_keyin_yechdi",
    "topshirishlar",
    "eng_yuqori_baho",
    "baho_manbasi",
    "birinchi_urinish",
    "oxirgi_urinish",
]

README = """\
Virtual laboratoriya: tadqiqot ma'lumotlari
==========================================

Fayllar CSV formatida, ajratuvchi — nuqtali vergul (;), kodlash — UTF-8.
Excel'da ikki marta bosib ochiladi. Python: pandas.read_csv("urinishlar.csv", sep=";")
Vaqtlar: {timezone} vaqt mintaqasida. Ha/yo'q qiymatlari: 1 / 0.
ai_yoqilgan: talabaning guruhida AI yordamchisi yoqilganmi (1 — tajriba guruhi, 0 — nazorat guruhi).
urinishlar.csv da urinish paytidagi holat, qolgan fayllarda eksport paytidagi guruh sozlamasi.
Eksport qilingan vaqt: {exported_at}

Anonimlik
---------
Talabaning ismi, logini va yozgan SQL kodi eksportga kirmaydi. «talaba» ustunidagi
taxallus (masalan, T-1A2B3C4D) har eksportda bir xil bo'ladi: turli eksportlarni va
laboratoriyalarni bitta talaba bo'yicha birlashtirish mumkin, lekin undan talabani
aniqlab bo'lmaydi. Kirish/chiqish testi natijalarini bog'lash kerak bo'lsa, taxallus
va ism ro'yxatini o'qituvchi alohida, maxfiy saqlaydi.

Rozilik
-------
{consent}

urinishlar.csv — har bir ishga tushirish
-----------------------------------------
talaba                      talaba taxallusi
guruh                       talabaning hozirgi guruhi
laboratoriya_id, laboratoriya
laboratoriya_turi           sql (SQL kod yozish) yoki er (ER-diagramma chizish)
urinish_raqami              shu talabaning shu laboratoriyadagi nechanchi urinishi (1 dan)
vaqt                        urinish vaqti
birinchi_urinishdan_daqiqa  shu laboratoriyadagi birinchi urinishdan beri o'tgan vaqt
turi                        ishga_tushirish yoki topshirish (baholashga)
natija                      togri | baza_xatosi (kod xato berdi) | natija_farqli (kod ishladi,
                            lekin natija namunadan farq qildi)
togri                       1 / 0
xato_turlari                xato toifalari, vergul bilan (pastdagi ro'yxatga qarang)
ai_maslahat                 talaba shu urinish uchun AI maslahatini olganmi: 1 / 0
maslahat_darajasi           olingan eng batafsil maslahat darajasi: 0 — olinmagan, 1 — yo'naltiruvchi
                            savol, 2 — tushuncha nomi, 3 — aniq ko'rsatma (darajalar joriy etilishidan
                            oldingi maslahatlar 3 deb yoziladi, chunki ular darhol batafsil berilgan)
kod_qatorlari, kod_belgilari  yozilgan kod hajmi (ER laboratoriyasida 0)
ishonch                     talaba tekshirishdan oldin belgilagan ishonch (1-5); bo'sh — belgilamagan

xulosa.csv — har bir talaba va laboratoriya
--------------------------------------------
Laboratoriya berilgan guruhdagi barcha faol talabalar kiradi, boshlamaganlari ham (urinishlar = 0).
urinishlar                  jami urinishlar
yechildi                    kamida bitta to'g'ri urinish bormi: 1 / 0
togri_gacha_urinishlar      birinchi to'g'ri urinishgacha (u ham kiradi) urinishlar soni
yechish_vaqti_daqiqa        birinchi urinishdan birinchi to'g'ri urinishgacha
baza_xatolari               kod xato bergan urinishlar soni
natija_farqlari             kod ishlagan, lekin natija farq qilgan urinishlar soni
ai_maslahatlar              olingan AI maslahatlari soni (maslahat olingan urinishlar)
maslahat_darajalari_jami    barcha urinishlardagi maslahat darajalari yig'indisi (jami so'ralgan yordam)
eng_yuqori_maslahat_darajasi  urinishlardagi eng yuqori maslahat darajasi (0 — maslahat olinmagan)
maslahatdan_keyin_yechdi    AI maslahatidan keyingi urinishlardan biri to'g'ri bo'lganmi: 1 / 0
                            (maslahat olinmagan bo'lsa bo'sh)
topshirishlar               baholashga topshirishlar soni
eng_yuqori_baho             0-100 (topshirmagan bo'lsa bo'sh)
baho_manbasi                ai (sun'iy intellekt) yoki auto (avtomatik tekshiruv)
birinchi_urinish, oxirgi_urinish

testlar.csv — har bir talaba va test (kirish/chiqish testlari)
-------------------------------------------------------------
Test berilgan guruhdagi barcha faol talabalar kiradi, topshirmaganlari ham.
test_id, test
test_turi                   kirish | chiqish | kechiktirilgan | oddiy | sorovnoma
holat                       topshirgan | boshlagan | boshlamagan
ball, maksimal_ball, foiz   topshirmagan bo'lsa va so'rovnomada bo'sh
boshlangan, topshirilgan
davomiylik_daqiqa           boshlangandan topshirilgangacha

test_javoblari.csv — har bir talabaning har bir savoldagi natijasi (savollar tahlili uchun)
------------------------------------------------------------------------------------------
test_id, test_turi
savol_raqami                testdagi tartib raqami (kirish va chiqish testlarida bir xil savollarni solishtirish uchun)
savol_turi                  bitta (bitta to'g'ri javob) | kop (bir nechta to'g'ri javob) |
                            likert (so'rovnoma fikri, ball qo'yilmaydi)
ball, maksimal_ball         savol bo'yicha (likert savolida bo'sh)
togri                       to'liq ball olganmi: 1 / 0 (likert savolida bo'sh)
javob                       faqat likert savolida: 1 — mutlaqo qo'shilmayman, 2 — qo'shilmayman,
                            3 — betarafman, 4 — qo'shilaman, 5 — to'liq qo'shilaman
                            (javob berilmagan bo'lsa bo'sh)

baholash_mosligi.csv — ko'r baholash: tizim va o'qituvchi bahosi juftliklari
--------------------------------------------------------------------------
O'qituvchi ishni talaba ismi va tizim bahosini ko'rmasdan baholagan.
baholovchi                  baholovchi taxallusi (O-...)
tizim_ball                  o'qituvchi baholagan paytdagi tizim bahosi (0-100)
tizim_manbasi               ai (sun'iy intellekt) yoki auto (avtomatik tekshiruv)
oqituvchi_ball              o'qituvchi bahosi (0-100)
farq                        tizim_ball − oqituvchi_ball (musbat — tizim yumshoqroq)
tizim_baho, oqituvchi_baho  5 ballik shkalada: 86+ → 5, 71-85 → 4, 55-70 → 3, 0-54 → 2

ozaro_baholash.csv — talabalarning bir-birining ER-diagrammasini baholashi
---------------------------------------------------------------------------
baholovchi, muallif         ikkala talabaning taxallusi
obyektlar, atributlar, boglanishlar, tushunarlilik  rubrika ballari (1 — ko'p xato ... 4 — to'liq to'g'ri)
baholovchi_ball             tuzilma mezonlari (obyektlar, atributlar, bog'lanishlar) bo'yicha 0-100
tizim_ball                  baholash paytida ishning namunaga mosligi (0-100)
aniqlik                     100 − |baholovchi_ball − tizim_ball|
foydali                     muallif izohni foydali deb belgiladimi (1 / 0; bo'sh — belgilamagan)
izoh_uzunligi               izoh belgilari soni (izoh matni eksportga kirmaydi)

ai_sifati.csv — o'qituvchilarning AI matnlariga bergan baholari
----------------------------------------------------------------
baholovchi                  o'qituvchi taxallusi (O-...)
turi                        hint (AI maslahati) yoki explanation (tushuntirish bo'yicha AI izohi)
daraja                      maslahat darajasi (1 dan); izohda 0
baho                        helpful (foydali), unclear (tushunarsiz), wrong (noto'g'ri), revealed (javobni aytib qo'ydi)

laboratoriyalar_tahlili.csv — har bir laboratoriyaning psixometrik tahlili (klassik test nazariyasi)
------------------------------------------------------------------------------------------------------
Har bir laboratoriya bitta "savol" sifatida: talaba bali = laboratoriya bahosi / 100 (topshirmagan — 0).
Faqat laboratoriyani boshlagan talabalar olinadi; {min_students} tadan kam bo'lsa ko'rsatkichlar bo'sh.
berilgan, boshlagan          laboratoriya berilgan va uni boshlagan talabalar soni
qiyinlik_p                  o'rtacha ball ulushi (0-1): qancha katta bo'lsa, shuncha oson
daraja, daraja_nomi         1 juda oson (p > 0.80), 2 oson (0.60-0.80), 3 o'rtacha (0.40-0.60),
                            4 qiyin (0.20-0.40), 5 juda qiyin (p ≤ 0.20)
ajratish_r                  tuzatilgan korrelyatsiya: laboratoriya bali va talabaning boshqa laboratoriyalardagi
                            o'rtacha bali (Pirson). Ebel: ≥ 0.40 a'lo, 0.30 yaxshi, 0.20 qoniqarli, < 0.20 past
ajratish_D                  yuqori va quyi 27% talabalar o'rtacha ballari farqi (har guruhda kamida 3 talaba)
alfa_olib_tashlansa         shu laboratoriyasiz Cronbach α (faqat ishonchlilik hisobidagi laboratoriyalar)
p_ai, p_nazorat             tajriba va nazorat guruhlarida qiyinlik (kamida 3 talaba)
yechganlar_foiz, birinchi_urinishda_foiz, yechish_urinishlari, yechish_daqiqa (mediana),
maslahat_olganlar_foiz      AI yoqilgan talabalardan maslahat olganlar ulushi
xulosa                      yaxshi | qayta_korib_chiqing | tekshiring_almashtiring
Oxirgi qator (laboratoriya_id = "alfa"): laboratoriyalar to'plamining Cronbach α si, unga kirgan
laboratoriyalar va talabalar soni (barcha guruhlarga berilgan va hammasini boshlagan talabalar).

kompetentlik.csv — har bir talaba, kesim va kompetentlik komponenti
---------------------------------------------------------------------
talaba, guruh, ai_yoqilgan
kesim                       boshida (tajriba boshida), oxirida (tajriba oxirida) yoki keyin (kechiktirilgan test)
komponent                   komponent nomi yoki "Umumiy" (o'lchangan komponentlar o'rtachasi)
ball                        0-100; bo'sh — bu kesimda o'lchanmagan (masalan, test topshirilmagan)
daraja                      past / orta / yuqori (chegaralar admin panelda, komponent sozlamalarida)
Ballar platformadagi kompetentlik modeli bo'yicha eksport paytida hisoblanadi.

Xato toifalari
--------------
Baza xatolari (kod ishlamadi):
{error_categories}
  juda_kop_qator, boshqa_xato

Namunadan farqlar (kod ishladi, natija boshqacha):
{difference_categories}
  boshqa_farq
"""


def pseudonym(user_id):
    digest = hmac.new(settings.SECRET_KEY.encode(), f"lab-research:{user_id}".encode(), hashlib.sha256)
    return "T-" + digest.hexdigest()[:8].upper()


def reviewer_pseudonym(user_id):
    digest = hmac.new(settings.SECRET_KEY.encode(), f"lab-reviewer:{user_id}".encode(), hashlib.sha256)
    return "O-" + digest.hexdigest()[:6].upper()


def _included(allowed, *student_ids):
    """Talaba(lar) tadqiqotga kiradimi: allowed None bo'lsa — hamma (rozilik talab qilinmaydi)."""
    return allowed is None or all(student_id in allowed for student_id in student_ids)


def _review_rows(labs, allowed=None):
    from .blind_review import band

    rows = []
    reviews = (
        BlindReview.objects.filter(attempt__lab__in=labs)
        .select_related("attempt__lab", "attempt__student__group")
        .order_by("attempt__lab_id", "id")
    )
    for review in reviews:
        attempt = review.attempt
        student = attempt.student
        if not _included(allowed, student.pk):
            continue
        rows.append(
            [
                pseudonym(student.pk),
                student.group.name if student.group else "",
                _flag(attempt.ai_enabled),
                attempt.lab_id,
                attempt.lab.title,
                attempt.lab.kind,
                reviewer_pseudonym(review.reviewer_id),
                review.ai_score,
                review.ai_source,
                review.score,
                review.ai_score - review.score,
                band(review.ai_score),
                band(review.score),
                _local(review.created_at),
            ]
        )
    return rows


def error_category(error):
    code = error.get("sqlstate") or TIP_TO_SQLSTATE.get(error.get("tip", ""), "")
    if code in ERROR_CATEGORIES:
        return ERROR_CATEGORIES[code]
    if "juda ko'p qator" in error.get("message", ""):
        return "juda_kop_qator"
    return "boshqa_xato"


def difference_category(text):
    return next((category for pattern, category in DIFFERENCE_CATEGORIES if pattern in text), "boshqa_farq")


def attempt_categories(attempt):
    error = attempt.feedback.get("error")
    if error:
        return [error_category(error)]
    categories = [difference_category(text) for text in attempt.feedback.get("differences") or []]
    # Tartib saqlanadi, takrorlar olib tashlanadi
    return list(dict.fromkeys(categories))


def attempt_outcome(attempt):
    if attempt.is_correct:
        return "togri"
    return "baza_xatosi" if attempt.feedback.get("error") else "natija_farqli"


def hint_level(attempt):
    """Olingan maslahat darajasi (0-3). Darajalargacha bo'lgan maslahat to'liq (3) hisoblanadi."""
    if attempt.ai_hint_level:
        return attempt.ai_hint_level
    return 3 if attempt.ai_advice else 0


def _local(moment):
    return timezone.localtime(moment).strftime("%Y-%m-%d %H:%M:%S") if moment else ""


def _minutes(start, end):
    return f"{(end - start).total_seconds() / 60:.1f}"


def _flag(value):
    return 1 if value else 0


def _csv(columns, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=DELIMITER, lineterminator="\r\n")
    writer.writerow(columns)
    writer.writerows(rows)
    # BOM: Excel o'zbekcha harflarni to'g'ri ko'rsatishi uchun
    return "﻿" + buffer.getvalue()


def _group_ai(student):
    return _flag(student.group.ai_enabled) if student.group else ""


def _summary_row(student_id, group, ai_enabled, lab, attempts, grade):
    row = {
        "talaba": pseudonym(student_id),
        "guruh": group,
        "ai_yoqilgan": ai_enabled,
        "laboratoriya_id": lab.pk,
        "laboratoriya": lab.title,
        "laboratoriya_turi": lab.kind,
        "urinishlar": len(attempts),
        "yechildi": 0,
        "togri_gacha_urinishlar": "",
        "yechish_vaqti_daqiqa": "",
        "baza_xatolari": sum(1 for attempt in attempts if attempt.feedback.get("error")),
        "natija_farqlari": sum(1 for attempt in attempts if attempt_outcome(attempt) == "natija_farqli"),
        "ai_maslahatlar": sum(1 for attempt in attempts if attempt.ai_advice),
        "maslahat_darajalari_jami": sum(hint_level(attempt) for attempt in attempts),
        "eng_yuqori_maslahat_darajasi": max((hint_level(attempt) for attempt in attempts), default=0),
        "maslahatdan_keyin_yechdi": "",
        "topshirishlar": sum(1 for attempt in attempts if attempt.is_submission),
        "eng_yuqori_baho": grade.score if grade else "",
        "baho_manbasi": grade.source if grade else "",
        "birinchi_urinish": _local(attempts[0].created_at) if attempts else "",
        "oxirgi_urinish": _local(attempts[-1].created_at) if attempts else "",
    }
    first_correct = next((index for index, attempt in enumerate(attempts) if attempt.is_correct), None)
    if first_correct is not None:
        row["yechildi"] = 1
        row["togri_gacha_urinishlar"] = first_correct + 1
        row["yechish_vaqti_daqiqa"] = _minutes(attempts[0].created_at, attempts[first_correct].created_at)
    first_advice = next((index for index, attempt in enumerate(attempts) if attempt.ai_advice), None)
    if first_advice is not None:
        row["maslahatdan_keyin_yechdi"] = _flag(any(attempt.is_correct for attempt in attempts[first_advice + 1 :]))
    return [row[column] for column in SUMMARY_COLUMNS]


def _quiz_rows(quizzes, allowed=None):
    """testlar.csv va test_javoblari.csv qatorlari."""
    from quizzes.models import QuizAttempt
    from quizzes.services import attempt_status, finalize_if_expired, likert_value, percent

    quiz_rows, answer_rows = [], []
    for quiz in sorted(quizzes.prefetch_related("groups", "questions__choices"), key=lambda item: item.pk):
        attempts = {
            attempt.student_id: finalize_if_expired(attempt)
            for attempt in QuizAttempt.objects.filter(quiz=quiz).select_related("quiz", "student__group")
        }
        members = research_participants(
            User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=quiz.groups.all())
        ).select_related("group")
        students = {student.pk: student.group.name for student in members}
        ai_of = {student.pk: _group_ai(student) for student in members}
        attempts = {student_id: attempt for student_id, attempt in attempts.items() if _included(allowed, student_id)}
        for student_id, attempt in attempts.items():
            students.setdefault(student_id, attempt.student.group.name if attempt.student.group else "")
            ai_of.setdefault(student_id, _group_ai(attempt.student))
        kind = QUIZ_KINDS.get(quiz.kind, quiz.kind)
        questions = list(quiz.questions.all())
        for student_id in sorted(students, key=pseudonym):
            attempt = attempts.get(student_id)
            submitted = bool(attempt and attempt.submitted_at)
            scored = submitted and quiz.kind != "survey"
            quiz_rows.append(
                [
                    pseudonym(student_id),
                    students[student_id],
                    ai_of[student_id],
                    quiz.pk,
                    quiz.title,
                    kind,
                    QUIZ_STATUSES[attempt_status(attempt)],
                    attempt.score if scored else "",
                    attempt.max_score if scored else "",
                    percent(attempt) if scored else "",
                    _local(attempt.started_at) if attempt else "",
                    _local(attempt.submitted_at) if submitted else "",
                    _minutes(attempt.started_at, attempt.submitted_at) if submitted else "",
                ]
            )
            if not submitted:
                continue
            for question in questions:
                earned = attempt.results.get(str(question.pk), 0)
                likert = question.kind == "likert"
                answer = likert_value(question, attempt.answers.get(str(question.pk), [])) if likert else None
                answer_rows.append(
                    [
                        pseudonym(student_id),
                        students[student_id],
                        quiz.pk,
                        kind,
                        question.order,
                        QUESTION_KINDS.get(question.kind, question.kind),
                        "" if likert else earned,
                        "" if likert else question.points,
                        "" if likert else _flag(earned >= question.points),
                        "" if answer is None else answer,
                    ]
                )
    return quiz_rows, answer_rows


PEER_REVIEW_COLUMNS = [
    "baholovchi",
    "muallif",
    "guruh",
    "ai_yoqilgan",
    "laboratoriya_id",
    "laboratoriya",
    "obyektlar",
    "atributlar",
    "boglanishlar",
    "tushunarlilik",
    "baholovchi_ball",
    "tizim_ball",
    "aniqlik",
    "foydali",
    "izoh_uzunligi",
    "vaqt",
]


def _peer_review_rows(labs, allowed=None):
    """O'zaro baholashlar: ikkala tomon taxallus bilan; izoh matni kirmaydi (unda ism bo'lishi mumkin), faqat uzunligi."""
    from .peer_review import accuracy, structural_score

    rows = []
    reviews = PeerReview.objects.filter(attempt__lab__in=labs).select_related("attempt__lab", "reviewer__group").order_by("id")
    for review in reviews:
        # Ikkala tomon ham rozi bo'lishi kerak
        if not _included(allowed, review.reviewer_id, review.attempt.student_id):
            continue
        group = review.reviewer.group
        rows.append(
            [
                pseudonym(review.reviewer_id),
                pseudonym(review.attempt.student_id),
                group.name if group else "",
                _flag(group.ai_enabled) if group else "",
                review.attempt.lab_id,
                review.attempt.lab.title,
                review.scores.get("entities"),
                review.scores.get("attributes"),
                review.scores.get("relationships"),
                review.scores.get("clarity"),
                round(structural_score(review.scores), 1),
                round(100 * review.reference_ratio, 1),
                round(accuracy(review), 1),
                "" if review.helpful is None else _flag(review.helpful),
                len(review.comment),
                _local(review.created_at),
            ]
        )
    return rows


AI_QUALITY_COLUMNS = ["baholovchi", "laboratoriya_id", "laboratoriya", "turi", "daraja", "baho", "vaqt"]


def _ai_quality_rows(labs, allowed=None):
    """O'qituvchilarning AI matnlariga bergan baholari (baholovchi taxallus bilan)."""
    reviews = AIOutputReview.objects.filter(attempt__lab__in=labs).select_related("attempt__lab").order_by("id")
    reviews = [review for review in reviews if _included(allowed, review.attempt.student_id)]
    return [
        [
            reviewer_pseudonym(review.reviewer_id),
            review.attempt.lab_id,
            review.attempt.lab.title,
            review.kind,
            review.level,
            review.rating,
            _local(review.created_at),
        ]
        for review in reviews
    ]


COMPETENCE_COLUMNS = ["talaba", "guruh", "ai_yoqilgan", "kesim", "komponent", "ball", "daraja"]
COMPETENCE_STAGES = {"initial": "boshida", "final": "oxirida", "delayed": "keyin"}
COMPETENCE_LEVELS = {"low": "past", "medium": "orta", "high": "yuqori"}


def _competence_rows(groups, allowed=None):
    """Kompetentlik modeli bo'yicha har bir talaba, kesim va komponent (hamda umumiy) bali va darajasi."""
    from competence.services import Data, group_students, load_model, student_profile

    components = load_model()
    if not components:
        return []
    rows = []
    for group in groups:
        students = [student for student in group_students(group) if _included(allowed, student.pk)]
        for stage, stage_label in COMPETENCE_STAGES.items():
            data = Data(components, students, stage)
            for student in students:
                scores, overall = student_profile(components, student, data)
                items = [(component.name, scores[component.pk]) for component in components] + [("Umumiy", overall)]
                for name, item in items:
                    rows.append(
                        [
                            pseudonym(student.pk),
                            group.name,
                            _flag(group.ai_enabled),
                            stage_label,
                            name,
                            "" if item["score"] is None else item["score"],
                            COMPETENCE_LEVELS.get(item["level"], ""),
                        ]
                    )
    stage_order = list(COMPETENCE_STAGES.values())
    rows.sort(key=lambda row: (row[0], stage_order.index(row[3])))
    return rows


LAB_ANALYSIS_COLUMNS = [
    "laboratoriya_id",
    "laboratoriya",
    "laboratoriya_turi",
    "mavzu",
    "berilgan",
    "boshlagan",
    "qiyinlik_p",
    "daraja",
    "daraja_nomi",
    "ajratish_r",
    "ajratish_D",
    "alfa_olib_tashlansa",
    "p_ai",
    "p_nazorat",
    "yechganlar_foiz",
    "birinchi_urinishda_foiz",
    "yechish_urinishlari",
    "yechish_daqiqa",
    "maslahat_olganlar_foiz",
    "xulosa",
]
VERDICT_CODES = {"good": "yaxshi", "review": "qayta_korib_chiqing", "replace": "tekshiring_almashtiring"}


def _blank(value):
    return "" if value is None else value


def _lab_analysis_rows(labs, groups):
    from .psychometrics import analyse

    result = analyse(labs, groups)
    rows = []
    for row in result["labs"]:
        cohorts = row["cohorts"] or {}
        rows.append(
            [
                row["id"],
                row["title"],
                row["kind"],
                row["topic"],
                row["assigned"],
                row["started"],
                _blank(row["p"]),
                row["level"]["number"] if row["level"] else "",
                row["level"]["label"] if row["level"] else "",
                _blank(row["r"]),
                _blank(row["d"]),
                _blank(row["alpha_if_deleted"]),
                _blank(cohorts.get("ai", {}).get("p")),
                _blank(cohorts.get("control", {}).get("p")),
                _blank(row["solved_rate"]),
                _blank(row["first_try_rate"]),
                _blank(row["attempts_to_solve"]),
                _blank(row["minutes_to_solve"]),
                _blank(row["hint_rate"]),
                VERDICT_CODES[row["verdict"]["key"]] if row["verdict"] else "",
            ]
        )
    reliability = result["reliability"]
    alpha_row = [""] * len(LAB_ANALYSIS_COLUMNS)
    alpha_row[0] = "alfa"
    alpha_row[1] = f"Cronbach alfa: {reliability['labs']} ta laboratoriya, {reliability['students']} ta talaba"
    alpha_row[6] = _blank(reliability["alpha"])
    rows.append(alpha_row)
    return rows


def build_export(labs, quizzes=None, groups=None):
    """Berilgan laboratoriyalar, testlar va guruhlar (kompetentlik) bo'yicha ZIP arxiv (bytes) qaytaradi.

    Rozilik talab qilinsa (RESEARCH_CONSENT_REQUIRED), faqat tadqiqotga rozi bo'lgan talabalar kiradi.
    """
    labs_queryset = labs
    labs = list(labs.prefetch_related("groups"))
    allowed = participant_ids()
    attempts = (
        LabAttempt.objects.filter(lab__in=labs)
        .select_related("student__group")
        .order_by("created_at", "id")
    )
    if allowed is not None:
        attempts = attempts.filter(student_id__in=allowed)
    by_pair = defaultdict(list)
    groups_of, ai_of = {}, {}
    for attempt in attempts:
        by_pair[(attempt.lab_id, attempt.student_id)].append(attempt)
        groups_of[attempt.student_id] = attempt.student.group.name if attempt.student.group else ""
        ai_of[attempt.student_id] = _group_ai(attempt.student)
    grades = {(grade.lab_id, grade.student_id): grade for grade in LabGrade.objects.filter(lab__in=labs)}

    attempt_rows = []
    summary_rows = []
    for lab in sorted(labs, key=lambda item: item.pk):
        # Laboratoriya berilgan guruhlarning faol talabalari (boshlamaganlari ham) va urinish qilganlar
        members = research_participants(
            User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=lab.groups.all())
        ).select_related("group")
        students = {student.pk: student.group.name for student in members}
        for student in members:
            ai_of.setdefault(student.pk, _group_ai(student))
        for (lab_id, student_id) in by_pair:
            if lab_id == lab.pk:
                students.setdefault(student_id, groups_of[student_id])

        for student_id in sorted(students, key=pseudonym):
            student_attempts = by_pair.get((lab.pk, student_id), [])
            group = students[student_id]
            for number, attempt in enumerate(student_attempts, start=1):
                attempt_rows.append(
                    [
                        pseudonym(student_id),
                        group,
                        _flag(attempt.ai_enabled),
                        lab.pk,
                        lab.title,
                        lab.kind,
                        number,
                        _local(attempt.created_at),
                        _minutes(student_attempts[0].created_at, attempt.created_at),
                        "topshirish" if attempt.is_submission else "ishga_tushirish",
                        attempt_outcome(attempt),
                        _flag(attempt.is_correct),
                        ",".join(attempt_categories(attempt)),
                        _flag(attempt.ai_advice),
                        hint_level(attempt),
                        len(attempt.sql_code.splitlines()),
                        len(attempt.sql_code),
                        "" if attempt.confidence is None else attempt.confidence,
                    ]
                )
            summary_rows.append(
                _summary_row(
                    student_id, group, ai_of[student_id], lab, student_attempts, grades.get((lab.pk, student_id))
                )
            )

    if consent_required():
        consent = (
            "Eksportga faqat ilmiy tadqiqotda ishtirok etishga rozilik bergan talabalar kiradi\n"
            f"(eksport paytida {len(allowed)} ta talaba). Rozilik bermagan yoki qaytarib olganlarning\n"
            "ma'lumotlari hech bir faylda yo'q; o'zaro baholashda ikkala tomon ham rozi bo'lishi kerak."
        )
    else:
        consent = "Rozilik talab qilinmagan (RESEARCH_CONSENT_REQUIRED=False): barcha talabalar kiradi."
    readme = README.format(
        consent=consent,
        min_students=MIN_ANALYSIS_STUDENTS,
        timezone=settings.TIME_ZONE,
        exported_at=_local(timezone.now()),
        error_categories="\n".join(f"  {name}" for name in dict.fromkeys(ERROR_CATEGORIES.values())),
        difference_categories="\n".join(
            f"  {name}" for name in dict.fromkeys(category for _, category in DIFFERENCE_CATEGORIES)
        ),
    )
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("urinishlar.csv", _csv(ATTEMPT_COLUMNS, attempt_rows))
        zip_file.writestr("xulosa.csv", _csv(SUMMARY_COLUMNS, summary_rows))
        zip_file.writestr("baholash_mosligi.csv", _csv(REVIEW_COLUMNS, _review_rows(labs, allowed)))
        zip_file.writestr("ozaro_baholash.csv", _csv(PEER_REVIEW_COLUMNS, _peer_review_rows(labs, allowed)))
        zip_file.writestr("ai_sifati.csv", _csv(AI_QUALITY_COLUMNS, _ai_quality_rows(labs, allowed)))
        if quizzes is not None:
            quiz_rows, answer_rows = _quiz_rows(quizzes, allowed)
            zip_file.writestr("testlar.csv", _csv(QUIZ_COLUMNS, quiz_rows))
            zip_file.writestr("test_javoblari.csv", _csv(ANSWER_COLUMNS, answer_rows))
        if groups is not None:
            zip_file.writestr("kompetentlik.csv", _csv(COMPETENCE_COLUMNS, _competence_rows(groups, allowed)))
            zip_file.writestr("laboratoriyalar_tahlili.csv", _csv(LAB_ANALYSIS_COLUMNS, _lab_analysis_rows(labs_queryset, groups)))
        zip_file.writestr("README.txt", readme)
    return archive.getvalue()
