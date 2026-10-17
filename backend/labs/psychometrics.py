"""Laboratoriyalarning psixometrik tahlili (klassik test nazariyasi): har bir laboratoriya — bitta "savol".

Har bir laboratoriya uchun:
- qiyinlik indeksi p: laboratoriyani boshlagan talabalar o'rtacha bahosining ulushi (baho / 100; topshirmagan — 0).
  p bo'yicha 5 daraja: 1 — juda oson (p > 0.80), 2 — oson (0.60-0.80), 3 — o'rtacha (0.40-0.60),
  4 — qiyin (0.20-0.40), 5 — juda qiyin (p ≤ 0.20);
- ajrata olish: tuzatilgan "laboratoriya — umumiy natija" korrelyatsiyasi r (talabaning boshqa laboratoriyalardagi
  o'rtacha bahosi bilan Pirson korrelyatsiyasi) va yuqori/quyi 27% guruhlar indeksi D = p(yuqori) − p(quyi);
  Ebel shkalasi: r ≥ 0.40 a'lo, 0.30-0.39 yaxshi, 0.20-0.29 qoniqarli, 0-0.19 past, manfiy — tekshiruvda xato bo'lishi mumkin;
- jarayon ko'rsatkichlari: birinchi urinishda yechganlar, yechish uchun urinishlar, AI maslahati olganlar, vaqt;
- tajriba (AI yoqilgan) va nazorat guruhlarida alohida qiyinlik.

Laboratoriyalar to'plamining ishonchliligi: Cronbach α (ichki muvofiqlik) — tanlangan barcha guruhlarga berilgan
umumiy laboratoriyalar va ularning hammasini boshlagan talabalar bo'yicha; har bir laboratoriya uchun
"olib tashlansa α". O'lchov xatosi SEM = SD·√(1 − α).

Faqat tadqiqotga rozi bo'lgan talabalar olinadi (users/consent.py). Hisob boshlagan talabalar bo'yicha:
yaqinda ochilgan laboratoriyani boshlamaganlar uni "qiyin" qilib ko'rsatmasligi uchun.
"""
import math
from collections import defaultdict
from statistics import median

from users.consent import consent_required, research_participants
from users.models import User

from .models import Lab, LabAttempt, LabGrade

# Laboratoriya tahlil qilinishi uchun uni boshlagan talabalar soni (kam bo'lsa ko'rsatkichlar tasodifiy)
MIN_STUDENTS = 5
# Yuqori va quyi guruhlar ulushi (Kelley) va har bir guruhdagi eng kam talaba soni
EXTREME_SHARE = 0.27
MIN_EXTREME = 3
# Bundan kam talabada natija dastlabki deb belgilanadi
RELIABLE_STUDENTS = 30

LEVELS = [
    # (raqam, kalit, nomi, p shu qiymatdan katta bo'lsa)
    (1, "very_easy", "Juda oson", 0.80),
    (2, "easy", "Oson", 0.60),
    (3, "medium", "O'rtacha", 0.40),
    (4, "hard", "Qiyin", 0.20),
    (5, "very_hard", "Juda qiyin", -math.inf),
]

DISCRIMINATION = [
    ("excellent", "A'lo", 0.40),
    ("good", "Yaxshi", 0.30),
    ("fair", "Qoniqarli", 0.20),
    ("poor", "Past", 0.0),
    ("negative", "Manfiy", -math.inf),
]

ALPHA_LEVELS = [
    ("excellent", "A'lo", 0.9),
    ("good", "Yaxshi", 0.8),
    ("acceptable", "Maqbul", 0.7),
    ("questionable", "Shubhali", 0.6),
    ("poor", "Past", 0.5),
    ("unacceptable", "Qabul qilinmaydi", -math.inf),
]

VERDICTS = {"good": "Yaxshi", "review": "Qayta ko'rib chiqing", "replace": "Tekshiring yoki almashtiring"}

# α shu qiymatdan ko'proq oshsa, laboratoriya to'plamni "buzyapti" deb hisoblanadi
ALPHA_GAIN = 0.02


def _round(value, digits=2):
    return None if value is None else round(value, digits)


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def _variance(values):
    """Tanlanma dispersiyasi (n − 1)."""
    values = list(values)
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def pearson(xs, ys):
    """Pirson korrelyatsiyasi; qiymatlardan biri o'zgarmas bo'lsa None."""
    if len(xs) < 3:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-12 or syy <= 1e-12:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def cronbach_alpha(matrix):
    """matrix — har bir talaba uchun bir xil tartibdagi laboratoriya ballari ro'yxati. Kamida 2 laboratoriya va 2 talaba."""
    if len(matrix) < 2 or len(matrix[0]) < 2:
        return None
    k = len(matrix[0])
    item_variances = [_variance(row[index] for row in matrix) for index in range(k)]
    total_variance = _variance(sum(row) for row in matrix)
    if not total_variance:
        return None
    return k / (k - 1) * (1 - sum(item_variances) / total_variance)


def level_of(p):
    if p is None:
        return None
    return next(item for item in LEVELS if p > item[3])


def _label(scale, value):
    if value is None:
        return None
    key, label, _ = next(item for item in scale if value >= item[2])
    return {"key": key, "label": label}


def _lab_scores(labs, students):
    """{(lab_id, student_id): ball 0-1} — laboratoriyani boshlagan talabalar uchun; jarayon ma'lumotlari bilan."""
    attempts = defaultdict(list)
    for attempt in LabAttempt.objects.filter(lab__in=labs, student__in=students).order_by("created_at", "id").only(
        "lab_id", "student_id", "is_correct", "ai_advice", "ai_hint_level", "ai_enabled", "created_at"
    ):
        attempts[(attempt.lab_id, attempt.student_id)].append(attempt)
    grades = {
        (grade.lab_id, grade.student_id): grade.score
        for grade in LabGrade.objects.filter(lab__in=labs, student__in=students).only("lab_id", "student_id", "score")
    }
    scores = {pair: min(grades.get(pair, 0), 100) / 100 for pair in attempts}
    return scores, attempts


def _process(pairs):
    """Jarayon ko'rsatkichlari: [(talaba, urinishlar)]."""
    first_try, to_solve, minutes, hints, ai_pairs = 0, [], [], 0, 0
    for _, items in pairs:
        first = next((index for index, attempt in enumerate(items) if attempt.is_correct), None)
        if first == 0:
            first_try += 1
        if first is not None:
            to_solve.append(first + 1)
            minutes.append((items[first].created_at - items[0].created_at).total_seconds() / 60)
        if items[0].ai_enabled:
            ai_pairs += 1
            if any(attempt.ai_advice or attempt.ai_hint_level for attempt in items):
                hints += 1
    started = len(pairs)
    return {
        "solved_rate": _round(100 * len(to_solve) / started, 1) if started else None,
        "first_try_rate": _round(100 * first_try / started, 1) if started else None,
        "attempts_to_solve": _round(_mean(to_solve), 1),
        "minutes_to_solve": _round(median(minutes), 1) if minutes else None,
        "hint_rate": _round(100 * hints / ai_pairs, 1) if ai_pairs else None,
    }


def analyse(labs, groups):
    """labs — Lab QuerySet, groups — guruhlar ro'yxati. Natija API va eksport uchun lug'at."""
    groups = list(groups)
    everyone = User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=groups)
    students = list(research_participants(everyone).select_related("group"))
    by_id = {student.pk: student for student in students}
    group_ids = {group.pk for group in groups}
    labs = list(labs.filter(groups__in=groups).distinct().prefetch_related("groups").order_by("created_at", "id"))
    scores, attempts = _lab_scores(labs, students)

    lab_groups = {lab.pk: {group.pk for group in lab.groups.all()} & group_ids for lab in labs}
    started = defaultdict(list)  # lab_id -> [talaba_id], boshlaganlar
    for lab_id, student_id in scores:
        started[lab_id].append(student_id)
    by_student = defaultdict(dict)  # talaba -> {lab_id: ball}
    for (lab_id, student_id), score in scores.items():
        by_student[student_id][lab_id] = score

    def rest_mean(student_id, lab_id):
        other = [value for key, value in by_student[student_id].items() if key != lab_id]
        return _mean(other)

    # ---- Ishonchlilik: barcha tanlangan guruhlarga berilgan va kamida MIN_STUDENTS boshlagan laboratoriyalar ----
    common = [
        lab for lab in labs if lab_groups[lab.pk] == group_ids and len(started[lab.pk]) >= MIN_STUDENTS
    ]
    complete = sorted(
        sid for sid in by_student if all(lab.pk in by_student[sid] for lab in common)
    )
    matrix = [[by_student[sid][lab.pk] for lab in common] for sid in complete]
    alpha = cronbach_alpha(matrix) if len(complete) >= MIN_STUDENTS else None
    alpha_without = {}
    if alpha is not None and len(common) > 2:
        for index, lab in enumerate(common):
            alpha_without[lab.pk] = cronbach_alpha([row[:index] + row[index + 1 :] for row in matrix])
    totals = [100 * sum(row) for row in matrix]
    total_variance = _variance(totals)
    sd = math.sqrt(total_variance) if total_variance else None

    rows = []
    for lab in labs:
        ids = sorted(started[lab.pk])
        values = [scores[(lab.pk, sid)] for sid in ids]
        assigned = sum(1 for student in students if student.group_id in lab_groups[lab.pk])
        row = {
            "id": lab.pk,
            "title": lab.title,
            "kind": lab.kind,
            "topic": lab.topic,
            "assigned": assigned,
            "started": len(ids),
            "analysed": len(ids) >= MIN_STUDENTS,
            "in_reliability": lab in common,
            **_process([(sid, attempts[(lab.pk, sid)]) for sid in ids]),
        }
        if not row["analysed"]:
            rows.append({**row, "p": None, "level": None, "r": None, "discrimination": None, "d": None,
                         "alpha_if_deleted": None, "cohorts": None, "verdict": None, "advice": []})
            continue

        p = _mean(values)
        number, key, label, _ = level_of(p)
        # Tuzatilgan korrelyatsiya: faqat boshqa laboratoriyalarni ham boshlagan talabalar
        paired = [(scores[(lab.pk, sid)], rest_mean(sid, lab.pk)) for sid in ids]
        paired = [(x, y) for x, y in paired if y is not None]
        r = pearson([x for x, _ in paired], [y for _, y in paired])

        d = None
        size = round(EXTREME_SHARE * len(paired))
        if size >= MIN_EXTREME:
            ranked = sorted(paired, key=lambda item: item[1])
            d = _mean(x for x, _ in ranked[-size:]) - _mean(x for x, _ in ranked[:size])

        cohorts = {}
        for cohort, enabled in (("ai", True), ("control", False)):
            part = [scores[(lab.pk, sid)] for sid in ids if bool(by_id[sid].group.ai_enabled) == enabled]
            cohorts[cohort] = {"students": len(part), "p": _round(_mean(part)) if len(part) >= MIN_EXTREME else None}

        without = alpha_without.get(lab.pk)
        advice = []
        if number == 5:
            advice.append("Juda qiyin: shartni aniqlashtiring, nazariyaga namuna qo'shing yoki oldingi mavzuni takrorlating.")
        elif number == 1:
            advice.append("Juda oson: talabalarni bilim darajasi bo'yicha ajratmaydi; qo'shimcha talab qo'shing.")
        if r is not None and r < 0:
            advice.append(
                "Kuchli talabalar bu laboratoriyani kuchsizlardan yomonroq bajargan: namunaviy yechim, yashirin test "
                "ma'lumotlari va baholashni tekshiring."
            )
        elif r is not None and r < 0.20:
            advice.append("Kuchli va kuchsiz talabalarni yaxshi ajratmaydi: shart boshqa ko'nikmani o'lchayotgan bo'lishi mumkin.")
        if without is not None and without > alpha + ALPHA_GAIN:
            advice.append("Olib tashlansa, laboratoriyalar to'plamining ishonchliligi (α) oshadi.")
        if r is not None and r < 0:
            verdict = "replace"
        elif advice:
            verdict = "review"
        else:
            verdict = "good"
        rows.append(
            {
                **row,
                "p": _round(p),
                "level": {"number": number, "key": key, "label": label},
                "r": _round(r),
                "discrimination": _label(DISCRIMINATION, r),
                "d": _round(d),
                "alpha_if_deleted": _round(without, 3),
                "cohorts": cohorts,
                "verdict": {"key": verdict, "label": VERDICTS[verdict]},
                "advice": advice,
            }
        )

    distribution = [
        {"number": number, "key": key, "label": label, "count": sum(1 for row in rows if row["level"] and row["level"]["key"] == key)}
        for number, key, label, _ in LEVELS
    ]
    return {
        "consent_required": consent_required(),
        "students": len(students),
        "excluded_no_consent": everyone.count() - len(students),
        "min_students": MIN_STUDENTS,
        "reliable_students": RELIABLE_STUDENTS,
        "levels": [{"number": number, "key": key, "label": label, "above": None if bound == -math.inf else bound}
                   for number, key, label, bound in LEVELS],
        "distribution": distribution,
        "reliability": {
            "alpha": _round(alpha, 3),
            "interpretation": _label(ALPHA_LEVELS, alpha),
            "labs": len(common),
            "students": len(complete),
            "mean": _round(_mean(totals) / len(common), 1) if totals and common else None,
            "sd": _round(sd / len(common), 1) if sd and common else None,
            "sem": _round(sd * math.sqrt(1 - alpha) / len(common), 1) if sd and alpha is not None and alpha < 1 else None,
        },
        "labs": rows,
    }


def lab_queryset(user):
    """Tahlil qilinadigan laboratoriyalar: admin — barchasi, o'qituvchi — o'zi yaratganlari (statistika kabi)."""
    return Lab.objects.all() if user.is_admin else Lab.objects.filter(author=user)
