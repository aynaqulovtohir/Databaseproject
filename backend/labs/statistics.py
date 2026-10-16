"""O'qituvchi uchun statistika paneli: laboratoriyalar, xatolar, AI ta'siri va guruhlar taqqoslashi.

Hisoblar shaxsiy ma'lumotsiz (faqat sonlar), o'qituvchi faqat o'z laboratoriyalari, testlari
va o'zi o'qitadigan guruhlar bo'yicha ko'radi; admin — hammasini.
"""
from collections import Counter, defaultdict
from statistics import median

from quizzes.models import Quiz, QuizAttempt
from quizzes.services import finalize_if_expired, percent
from users.models import StudentGroup, User

from .models import Lab, LabAttempt, LabGrade
from .research import attempt_categories

TOP_ERRORS = 10

# Xato toifalarining o'qituvchi uchun o'zbekcha nomlari (research.py dagi toifalar)
CATEGORY_LABELS = {
    "sintaksis": "Sintaksis xatosi",
    "jadval_topilmadi": "Jadval topilmadi",
    "ustun_topilmadi": "Ustun topilmadi",
    "jadval_takrorlandi": "Jadval ikki marta yaratilgan",
    "ustun_takrorlandi": "Ustun takrorlangan",
    "ustun_noaniq": "Ustun nomi noaniq (qaysi jadvalniki?)",
    "group_by": "GROUP BY xatosi",
    "funksiya_yoki_operator": "Funksiya yoki operator xatosi",
    "tur_mos_emas": "Ma'lumot turlari mos emas",
    "tur_topilmadi": "Noma'lum ma'lumot turi",
    "fk_kalitsiz_ustunga": "FK kalit bo'lmagan ustunga ulangan",
    "jadval_tarifi_xato": "Jadval ta'rifi xato",
    "ruxsat_yoq": "Ruxsat yo'q",
    "qiymat_turi": "Qiymat ustun turiga mos emas",
    "matn_uzun": "Matn juda uzun",
    "son_chegarasi": "Son chegaradan chiqdi",
    "nolga_bolish": "Nolga bo'lish",
    "ichki_sorov_kop_qator": "Ichki so'rov ko'p qator qaytardi",
    "not_null_buzildi": "NOT NULL buzildi",
    "fk_buzildi": "Tashqi kalit buzildi",
    "unique_buzildi": "UNIQUE buzildi",
    "check_buzildi": "CHECK buzildi",
    "vaqt_tugadi": "Juda uzoq ishladi",
    "juda_kop_qator": "Juda ko'p qator",
    "boshqa_xato": "Boshqa baza xatosi",
    "pk_yetishmaydi": "PRIMARY KEY yetishmaydi",
    "fk_yetishmaydi": "FOREIGN KEY yetishmaydi",
    "unique_yetishmaydi": "UNIQUE yetishmaydi",
    "check_yetishmaydi": "CHECK yetishmaydi",
    "cheklov_yetishmaydi": "Cheklov yetishmaydi",
    "ustun_turi": "Ustun turi noto'g'ri",
    "not_null_yetishmaydi": "NOT NULL yetishmaydi",
    "ortiqcha_not_null": "Ortiqcha NOT NULL",
    "jadval_yetishmaydi": "Jadval yetishmaydi",
    "ortiqcha_jadval": "Ortiqcha jadval",
    "ustun_yetishmaydi": "Ustun yetishmaydi",
    "ortiqcha_ustun": "Ortiqcha ustun",
    "jadval_qiymatlari": "Jadvaldagi qiymatlar xato",
    "jadval_qatorlari_soni": "Jadval qatorlari soni xato",
    "select_yoq": "Oxirida SELECT yo'q",
    "natija_ustunlari_soni": "Natija ustunlari soni xato",
    "natija_qatorlari_soni": "Natija qatorlari soni xato",
    "natija_tartibi": "Natija tartibi (ORDER BY) xato",
    "natija_qiymatlari": "Natija qiymatlari xato",
    "er_obyekt_yetishmaydi": "ER: obyekt yetishmaydi",
    "er_ortiqcha_obyekt": "ER: ortiqcha obyekt",
    "er_atribut_yetishmaydi": "ER: atribut yetishmaydi",
    "er_ortiqcha_atribut": "ER: ortiqcha atribut",
    "er_asosiy_kalit": "ER: asosiy kalit xato",
    "er_mn_oraliq_obyekt": "ER: M:N oraliq obyekt orqali",
    "er_kardinallik": "ER: kardinallik xato",
    "er_boglanish_yetishmaydi": "ER: bog'lanish yetishmaydi",
    "er_ortiqcha_boglanish": "ER: ortiqcha bog'lanish",
    "er_bosh_diagramma": "ER: bo'sh diagramma",
    "boshqa_farq": "Boshqa farq",
}


def _round(value, digits=1):
    return round(value, digits) if value is not None else None


def _rate(part, whole):
    return _round(100 * part / whole) if whole else None


def _mean(values):
    values = [value for value in values if value is not None]
    return _round(sum(values) / len(values)) if values else None


def learning_order(labs, by_pair):
    """Laboratoriyalar talabalar ularni bajargan tartibda: har bir talabaning birinchi urinishi vaqtining
    medianasi bo'yicha. Hali boshlanmaganlari oxirida, talabalar ro'yxatda ko'radigan tartibda
    (yangisi yuqorida — seed_design_labs 1-laboratoriyani eng oxirida yaratadi)."""
    starts = defaultdict(list)
    for (lab_id, _), attempts in by_pair.items():
        starts[lab_id].append(attempts[0].created_at.timestamp())
    started = sorted((lab for lab in labs if starts[lab.pk]), key=lambda lab: (median(starts[lab.pk]), lab.pk))
    waiting = sorted(
        (lab for lab in labs if not starts[lab.pk]), key=lambda lab: (lab.created_at, lab.pk), reverse=True
    )
    return started + waiting


def allowed_groups(user):
    """Statistika ko'rish mumkin bo'lgan guruhlar: admin — hammasi, o'qituvchi — o'zi o'qitadiganlari."""
    groups = StudentGroup.objects.all() if user.is_admin else user.teaching_groups.all()
    return groups.order_by("name")


def build_statistics(user, group=None):
    groups = list(allowed_groups(user) if group is None else [group])
    labs_qs = Lab.objects.all() if user.is_admin else Lab.objects.filter(author=user)
    quizzes_qs = Quiz.objects.all() if user.is_admin else Quiz.objects.filter(author=user)

    students = list(
        User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=groups).select_related("group")
    )
    student_ids = {student.pk for student in students}
    students_by_id = {student.pk: student for student in students}
    group_of = {student.pk: student.group_id for student in students}

    labs = list(labs_qs.filter(groups__in=groups).distinct().prefetch_related("groups"))
    # Har bir laboratoriya qaysi talabalarga berilgan (laboratoriya guruhlari ∩ tanlangan guruhlar)
    assigned = {
        lab.pk: {sid for sid in student_ids if group_of[sid] in {item.pk for item in lab.groups.all()}} for lab in labs
    }
    attempts = list(
        LabAttempt.objects.filter(lab__in=labs, student_id__in=student_ids).order_by("created_at", "id")
    )
    by_pair = defaultdict(list)
    for attempt in attempts:
        by_pair[(attempt.lab_id, attempt.student_id)].append(attempt)
    grades = {
        (grade.lab_id, grade.student_id): grade.score
        for grade in LabGrade.objects.filter(lab__in=labs, student_id__in=student_ids)
    }

    labs = learning_order(labs, by_pair)

    def solved(lab_id, student_id):
        return any(attempt.is_correct for attempt in by_pair.get((lab_id, student_id), []))

    # ---- Umumiy ko'rsatkichlar ----
    pairs_total = sum(len(ids) for ids in assigned.values())
    pairs_solved = sum(1 for lab_id, ids in assigned.items() for sid in ids if solved(lab_id, sid))
    overview = {
        "students": len(students),
        "labs": len(labs),
        "attempts": len(attempts),
        "solved_rate": _rate(pairs_solved, pairs_total),
        "average_grade": _mean(grades.values()),
    }

    # ---- Eng ko'p uchragan xatolar (har bir urinishdagi har bir toifa bir marta) ----
    errors = Counter()
    for attempt in attempts:
        if not attempt.is_correct:
            errors.update(attempt_categories(attempt))
    top_errors = [
        {"category": category, "label": CATEGORY_LABELS.get(category, category), "count": count}
        for category, count in errors.most_common(TOP_ERRORS)
    ]

    def attempts_to_solve(lab_id, ids):
        """Yechgan talabalarning birinchi to'g'ri urinishgacha bo'lgan urinishlari soni."""
        result = []
        for sid in ids:
            pair = by_pair.get((lab_id, sid), [])
            first = next((index for index, attempt in enumerate(pair) if attempt.is_correct), None)
            if first is not None:
                result.append(first + 1)
        return result

    # ---- Laboratoriyalar qiyinligi ----
    lab_rows = []
    for lab in labs:
        ids = assigned[lab.pk]
        to_solve = attempts_to_solve(lab.pk, ids)
        started = sum(1 for sid in ids if by_pair.get((lab.pk, sid)))
        lab_rows.append(
            {
                "id": lab.pk,
                "title": lab.title,
                "kind": lab.kind,
                "students": len(ids),
                "started": started,
                "solved": len(to_solve),
                "solved_rate": _rate(len(to_solve), len(ids)),
                "attempts_to_solve": _mean(to_solve),
                "average_grade": _mean([grades.get((lab.pk, sid)) for sid in ids]),
            }
        )

    # ---- O'rganish egri chizig'i: laboratoriyadan laboratoriyaga yechish osonlashib boradimi ----
    ai_students = {sid for sid in student_ids if students_by_id[sid].group.ai_enabled}
    segments = {"ai": ai_students, "control": student_ids - ai_students}
    learning_curve = []
    for position, lab in enumerate(labs, start=1):
        point = {"id": lab.pk, "position": position, "title": lab.title, "kind": lab.kind}
        for name, members in segments.items():
            ids = assigned[lab.pk] & members
            to_solve = attempts_to_solve(lab.pk, ids)
            point[name] = {
                "students": len(ids),
                "solved": len(to_solve),
                "attempts_to_solve": _mean(to_solve),
                "first_try_rate": _rate(sum(1 for value in to_solve if value == 1), len(ids)),
            }
        learning_curve.append(point)

    # ---- AI maslahatining ta'siri: kamida bir marta xato qilgan (talaba, laboratoriya) juftliklari ----
    with_advice = {"pairs": 0, "solved": 0}
    without_advice = {"pairs": 0, "solved": 0}
    for pair in by_pair.values():
        first_wrong = next((index for index, attempt in enumerate(pair) if not attempt.is_correct), None)
        if first_wrong is None:
            continue
        advice_at = next((index for index, attempt in enumerate(pair) if attempt.ai_advice), None)
        bucket = with_advice if advice_at is not None else without_advice
        bucket["pairs"] += 1
        start = advice_at + 1 if advice_at is not None else first_wrong + 1
        if any(attempt.is_correct for attempt in pair[start:]):
            bucket["solved"] += 1
    ai_effect = {
        "with_advice": {**with_advice, "rate": _rate(with_advice["solved"], with_advice["pairs"])},
        "without_advice": {**without_advice, "rate": _rate(without_advice["solved"], without_advice["pairs"])},
    }

    # ---- Guruhlar taqqoslashi (kirish va chiqish testlari bilan) ----
    quizzes = list(quizzes_qs.filter(groups__in=groups).distinct().prefetch_related("groups"))
    quiz_percents = defaultdict(lambda: {"pre": [], "post": []})
    for attempt in QuizAttempt.objects.filter(
        quiz__in=[quiz for quiz in quizzes if quiz.kind in ("pre", "post")], student_id__in=student_ids
    ).select_related("quiz"):
        attempt = finalize_if_expired(attempt)
        if attempt.submitted_at:
            quiz_percents[group_of[attempt.student_id]][attempt.quiz.kind].append(percent(attempt))

    group_rows = []
    for item in groups:
        members = {sid for sid in student_ids if group_of[sid] == item.pk}
        group_pairs = [(lab_id, sid) for lab_id, ids in assigned.items() for sid in ids if sid in members]
        pre = _mean(quiz_percents[item.pk]["pre"])
        post = _mean(quiz_percents[item.pk]["post"])
        group_rows.append(
            {
                "id": item.pk,
                "name": item.name,
                "ai_enabled": item.ai_enabled,
                "students": len(members),
                "solved_rate": _rate(sum(1 for pair in group_pairs if solved(*pair)), len(group_pairs)),
                "average_grade": _mean([grades.get(pair) for pair in group_pairs]),
                "pre_test": pre,
                "post_test": post,
                "pre_count": len(quiz_percents[item.pk]["pre"]),
                "post_count": len(quiz_percents[item.pk]["post"]),
                "gain": _round(post - pre) if pre is not None and post is not None else None,
            }
        )

    return {
        "groups_available": [{"id": item.pk, "name": item.name} for item in allowed_groups(user)],
        "overview": overview,
        "top_errors": top_errors,
        "labs": lab_rows,
        "learning_curve": learning_curve,
        "ai_effect": ai_effect,
        "groups": group_rows,
    }
