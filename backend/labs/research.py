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

from users.models import User

from .checker import ERROR_TIPS
from .models import LabAttempt, LabGrade

QUIZ_KINDS = {"pre": "kirish", "post": "chiqish", "practice": "oddiy"}
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
test_turi                   kirish | chiqish | oddiy
holat                       topshirgan | boshlagan | boshlamagan
ball, maksimal_ball, foiz   topshirmagan bo'lsa bo'sh
boshlangan, topshirilgan
davomiylik_daqiqa           boshlangandan topshirilgangacha

test_javoblari.csv — har bir talabaning har bir savoldagi natijasi (savollar tahlili uchun)
------------------------------------------------------------------------------------------
test_id, test_turi
savol_raqami                testdagi tartib raqami (kirish va chiqish testlarida bir xil savollarni solishtirish uchun)
savol_turi                  bitta (bitta to'g'ri javob) | kop (bir nechta to'g'ri javob)
ball, maksimal_ball         savol bo'yicha
togri                       to'liq ball olganmi: 1 / 0

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


def _quiz_rows(quizzes):
    """testlar.csv va test_javoblari.csv qatorlari."""
    from quizzes.models import QuizAttempt
    from quizzes.services import attempt_status, finalize_if_expired, percent

    quiz_rows, answer_rows = [], []
    for quiz in sorted(quizzes.prefetch_related("groups", "questions"), key=lambda item: item.pk):
        attempts = {
            attempt.student_id: finalize_if_expired(attempt)
            for attempt in QuizAttempt.objects.filter(quiz=quiz).select_related("quiz", "student__group")
        }
        members = User.objects.filter(
            role=User.Role.STUDENT, is_active=True, group__in=quiz.groups.all()
        ).select_related("group")
        students = {student.pk: student.group.name for student in members}
        ai_of = {student.pk: _group_ai(student) for student in members}
        for student_id, attempt in attempts.items():
            students.setdefault(student_id, attempt.student.group.name if attempt.student.group else "")
            ai_of.setdefault(student_id, _group_ai(attempt.student))
        kind = QUIZ_KINDS.get(quiz.kind, quiz.kind)
        questions = list(quiz.questions.all())
        for student_id in sorted(students, key=pseudonym):
            attempt = attempts.get(student_id)
            submitted = bool(attempt and attempt.submitted_at)
            quiz_rows.append(
                [
                    pseudonym(student_id),
                    students[student_id],
                    ai_of[student_id],
                    quiz.pk,
                    quiz.title,
                    kind,
                    QUIZ_STATUSES[attempt_status(attempt)],
                    attempt.score if submitted else "",
                    attempt.max_score if submitted else "",
                    percent(attempt) if submitted else "",
                    _local(attempt.started_at) if attempt else "",
                    _local(attempt.submitted_at) if submitted else "",
                    _minutes(attempt.started_at, attempt.submitted_at) if submitted else "",
                ]
            )
            if not submitted:
                continue
            for question in questions:
                earned = attempt.results.get(str(question.pk), 0)
                answer_rows.append(
                    [
                        pseudonym(student_id),
                        students[student_id],
                        quiz.pk,
                        kind,
                        question.order,
                        "bitta" if question.kind == "single" else "kop",
                        earned,
                        question.points,
                        _flag(earned >= question.points),
                    ]
                )
    return quiz_rows, answer_rows


def build_export(labs, quizzes=None):
    """Berilgan laboratoriyalar va testlar bo'yicha ZIP arxiv (bytes) qaytaradi."""
    labs = list(labs.prefetch_related("groups"))
    attempts = (
        LabAttempt.objects.filter(lab__in=labs)
        .select_related("student__group")
        .order_by("created_at", "id")
    )
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
        members = User.objects.filter(
            role=User.Role.STUDENT, is_active=True, group__in=lab.groups.all()
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
                    ]
                )
            summary_rows.append(
                _summary_row(
                    student_id, group, ai_of[student_id], lab, student_attempts, grades.get((lab.pk, student_id))
                )
            )

    readme = README.format(
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
        if quizzes is not None:
            quiz_rows, answer_rows = _quiz_rows(quizzes)
            zip_file.writestr("testlar.csv", _csv(QUIZ_COLUMNS, quiz_rows))
            zip_file.writestr("test_javoblari.csv", _csv(ANSWER_COLUMNS, answer_rows))
        zip_file.writestr("README.txt", readme)
    return archive.getvalue()
