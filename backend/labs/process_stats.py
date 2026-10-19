"""ER-diagramma chizish jarayoni bo'yicha tadqiqot statistikasi (labs/process.py ko'rsatkichlari asosida).

Uchta savol:
1. Strategiyalar va natija: har bir strategiyada nechta ish, o'rtacha baho, yechganlar ulushi; strategiya × yechildi
   (Pirson χ²) va strategiyalar bo'yicha baholar (Kraskel–Uollis H).
2. AI ta'siri: tajriba (AI yoqilgan) va nazorat guruhlarining o'rtacha yaqinlashish egri chizig'i (vaqt normallashtiriladi:
   0% — birinchi holat, 100% — oxirgisi), strategiyalar taqsimoti (χ²) va jarayon ko'rsatkichlari (mezon shartlarga qarab
   avtomatik: quizzes/experiment.compare_independent). Bitta talaba bir nechta laboratoriyada ishlagan bo'lsa,
   ko'rsatkichlari o'rtachalanadi — har bir talaba bitta kuzatuv (mustaqillik sharti).
3. Strategiya o'zgarishi: kamida ikkita ER laboratoriyasida strategiyasi aniqlangan talabalarning birinchi va oxirgi
   laboratoriyadagi strategiyasi (o'tish jadvali).

Faqat tadqiqotga rozi bo'lgan talabalar; o'qituvchi faqat o'z laboratoriyalari va o'zi o'qitadigan guruhlarini ko'radi.
"""
from collections import Counter, defaultdict

from competence.stats import ALPHA, chi_square, kruskal_wallis
from quizzes.experiment import COHORTS, MIN_GROUP, _effect_label, _p_text, _r, compare_independent
from users.consent import research_participants
from users.models import User

from .models import ErSnapshot, Lab, LabAttempt, LabGrade
from .process import STRATEGIES, analyse, build_points, metrics

# Egri chiziq nuqtalari: 0%, 5%, ..., 100%
CURVE_POINTS = 21
# Tahlil qilinadigan strategiyalar ("aniqlanmadi" — hodisalar kam, solishtiruvga kirmaydi)
KNOWN_STRATEGIES = [key for key in STRATEGIES if key != "aniqlanmadi"]

METRICS = {
    "active_minutes": "Faol vaqt (daqiqa)",
    "checks": "Tekshiruvlar soni",
    "churn": "Qaytarish ulushi (o'chirilgan / qo'shilgan)",
    "first_relationship_minutes": "Birinchi bog'lanishgacha (daqiqa)",
    "entities_first_share": "Obyektlarning bog'lanishdan oldin chizilgan ulushi",
    "first_check_ratio": "Birinchi tekshiruvdagi moslik",
    "final_ratio": "Yakuniy moslik",
}


def er_labs(user):
    labs = Lab.objects.all() if user.is_admin else Lab.objects.filter(author=user)
    return labs.filter(kind=Lab.Kind.ER).exclude(reference_diagram=None)


def curve(steps, points=CURVE_POINTS):
    """Moslik normallashtirilgan vaqt bo'yicha: har bir nuqtada shu paytgacha erishilgan oxirgi moslik."""
    ratios = [(step["minutes"], step["ratio"] or 0.0) for step in steps]
    total = ratios[-1][0]
    result = []
    for index in range(points):
        moment = total * index / (points - 1)
        value = ratios[0][1]
        for minutes, ratio in ratios:
            if minutes > moment:
                break
            value = ratio
        result.append(value)
    return result


def _mean(values):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def _chi(table):
    result = chi_square(table)
    if result is None:
        return None
    return {
        "chi2": _r(result["chi2"]),
        "df": result["df"],
        "p": _r(result["p"], 4),
        "significant": result["p"] < ALPHA,
        "cramers_v": _r(result["cramers_v"]),
        "effect_label": _effect_label("r", result["cramers_v"]),
        "reliable": result["reliable"],
    }


def collect(labs, groups):
    """Har bir (laboratoriya, talaba) juftligi: ko'rsatkichlar, egri chiziq, baho, yechildi, guruh turi."""
    students = {
        student.pk: student
        for student in research_participants(
            User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=groups)
        ).select_related("group")
    }
    labs = {lab.pk: lab for lab in labs}
    snapshots, attempts = defaultdict(list), defaultdict(list)
    for item in ErSnapshot.objects.filter(lab_id__in=labs, student_id__in=students).order_by("created_at", "id"):
        snapshots[(item.lab_id, item.student_id)].append(item)
    for item in LabAttempt.objects.filter(lab_id__in=labs, student_id__in=students).order_by("created_at", "id"):
        attempts[(item.lab_id, item.student_id)].append(item)
    grades = {
        (grade.lab_id, grade.student_id): grade.score
        for grade in LabGrade.objects.filter(lab_id__in=labs, student_id__in=students)
    }
    rows = []
    for lab_id, student_id in snapshots.keys() | attempts.keys():
        steps = analyse(build_points(snapshots[(lab_id, student_id)], attempts[(lab_id, student_id)]), labs[lab_id].reference_diagram)
        if not steps:
            continue
        student = students[student_id]
        rows.append(
            {
                "lab": lab_id,
                "student": student_id,
                "cohort": "experimental" if student.group.ai_enabled else "control",
                "started": steps[0]["at"],
                "metrics": metrics(steps),
                "curve": curve(steps),
                "grade": grades.get((lab_id, student_id)),
                "solved": any(attempt.is_correct for attempt in attempts[(lab_id, student_id)]),
            }
        )
    return rows


def strategy_section(rows):
    by_strategy = defaultdict(list)
    for row in rows:
        by_strategy[row["metrics"]["strategy"]].append(row)
    items = []
    for key, label in STRATEGIES.items():
        group = by_strategy.get(key, [])
        grades = [row["grade"] for row in group if row["grade"] is not None]
        items.append(
            {
                "strategy": key,
                "label": label,
                "count": len(group),
                "share": _r(len(group) / len(rows), 3) if rows else None,
                "mean_grade": _r(_mean(grades), 1),
                "solved_rate": _r(sum(row["solved"] for row in group) / len(group), 3) if group else None,
                "by_cohort": {cohort: sum(1 for row in group if row["cohort"] == cohort) for cohort in COHORTS},
            }
        )
    solved_table = [
        [sum(1 for row in by_strategy[key] if row["solved"]), sum(1 for row in by_strategy[key] if not row["solved"])]
        for key in KNOWN_STRATEGIES
    ]
    graded = [[row["grade"] for row in by_strategy[key] if row["grade"] is not None] for key in KNOWN_STRATEGIES]
    kruskal = kruskal_wallis([sample for sample in graded if len(sample) >= MIN_GROUP])
    cohort_table = [[sum(1 for row in by_strategy[key] if row["cohort"] == cohort) for key in KNOWN_STRATEGIES] for cohort in COHORTS]
    return {
        "items": items,
        "solved_test": _chi(solved_table),
        "grade_test": None
        if kruskal is None
        else {
            "h": _r(kruskal["h"]),
            "df": kruskal["df"],
            "p": _r(kruskal["p"], 4),
            "significant": kruskal["p"] < ALPHA,
            "epsilon2": _r(kruskal["epsilon2"]),
            "effect_label": _effect_label("eta2", kruskal["epsilon2"]),
        },
        "cohort_test": _chi(cohort_table),
    }


def cohort_section(rows):
    curves = {}
    for cohort in COHORTS:
        group = [row["curve"] for row in rows if row["cohort"] == cohort]
        curves[cohort] = {
            "n": len(group),
            "points": [_r(sum(values) / len(group), 3) for values in zip(*group)] if group else [],
        }
    # Har bir talaba bitta kuzatuv: laboratoriyalar bo'yicha o'rtacha
    per_student = defaultdict(lambda: defaultdict(list))
    cohort_of = {}
    for row in rows:
        cohort_of[row["student"]] = row["cohort"]
        for key in METRICS:
            if row["metrics"][key] is not None:
                per_student[row["student"]][key].append(row["metrics"][key])
    comparisons = []
    for key, label in METRICS.items():
        values = {cohort: [] for cohort in COHORTS}
        for student_id, items in per_student.items():
            if items[key]:
                values[cohort_of[student_id]].append(sum(items[key]) / len(items[key]))
        comparisons.append(
            {
                "metric": key,
                "label": label,
                "experimental": {"n": len(values["experimental"]), "mean": _r(_mean(values["experimental"]))},
                "control": {"n": len(values["control"]), "mean": _r(_mean(values["control"]))},
                "test": compare_independent(values["experimental"], values["control"]),
            }
        )
    return {"curves": curves, "comparisons": comparisons}


def transition_section(rows):
    by_student = defaultdict(list)
    for row in rows:
        if row["metrics"]["strategy"] in KNOWN_STRATEGIES:
            by_student[row["student"]].append(row)
    counts = Counter()
    for items in by_student.values():
        if len(items) < 2:
            continue
        items.sort(key=lambda row: row["started"])
        counts[(items[0]["metrics"]["strategy"], items[-1]["metrics"]["strategy"])] += 1
    return {
        "strategies": [{"strategy": key, "label": STRATEGIES[key]} for key in KNOWN_STRATEGIES],
        "students": sum(counts.values()),
        "matrix": [[counts[(first, last)] for last in KNOWN_STRATEGIES] for first in KNOWN_STRATEGIES],
    }


def conclusions(strategies, cohorts, transitions):
    lines = []
    known = sum(item["count"] for item in strategies["items"] if item["strategy"] in KNOWN_STRATEGIES)
    if known:
        top = max((item for item in strategies["items"] if item["strategy"] in KNOWN_STRATEGIES), key=lambda item: item["count"])
        lines.append(f"Eng ko'p uchragan strategiya — «{top['label']}» ({top['count']} ta ish, {round(100 * top['count'] / known)}%).")
    test = strategies["grade_test"]
    if test:
        verdict = "ahamiyatli farq qiladi" if test["significant"] else "statistik ahamiyatli farq qilmaydi"
        lines.append(
            f"Strategiyalar bo'yicha baholar {verdict} (Kraskel–Uollis H = {test['h']}, {_p_text(test['p'])}, ε² = {test['epsilon2']})."
        )
    test = strategies["cohort_test"]
    if test:
        verdict = "farq qiladi" if test["significant"] else "statistik ahamiyatli farq qilmaydi"
        note = "" if test["reliable"] else " Diqqat: kataklardagi kutilgan son 5 dan kam, natija taxminiy."
        lines.append(
            f"Tajriba va nazorat guruhlarida strategiyalar taqsimoti {verdict} (χ² = {test['chi2']}, {_p_text(test['p'])}, "
            f"Kramer V = {test['cramers_v']}).{note}"
        )
    for item in cohorts["comparisons"]:
        test = item["test"]
        if test and test["significant"]:
            higher = "tajriba" if item["experimental"]["mean"] > item["control"]["mean"] else "nazorat"
            lines.append(
                f"«{item['label']}» {higher} guruhida yuqori ({test['label']}, {_p_text(test['p'])}, "
                f"{test['effect']['name']} = {test['effect']['value']}, {test['effect']['label']} effekt)."
            )
    if not any(item["test"] for item in cohorts["comparisons"]):
        lines.append(f"Guruhlarni solishtirish uchun har birida kamida {MIN_GROUP} ta talabaning jarayoni kerak.")
    if transitions["students"]:
        stayed = sum(transitions["matrix"][index][index] for index in range(len(KNOWN_STRATEGIES)))
        lines.append(
            f"Kamida ikkita laboratoriyada ishlagan {transitions['students']} talabadan {stayed} tasi strategiyasini saqlagan."
        )
    return lines


def build(user, groups, lab=None):
    labs = list(er_labs(user).filter(groups__in=groups).distinct().order_by("pk"))
    selected = [item for item in labs if lab is None or item.pk == lab]
    rows = collect(selected, groups)
    strategies = strategy_section(rows)
    cohorts = cohort_section(rows)
    transitions = transition_section(rows)
    return {
        "labs": [{"id": item.pk, "title": item.title} for item in labs],
        "works": len(rows),
        "students": len({row["student"] for row in rows}),
        "cohorts": COHORTS,
        "strategies": strategies,
        "cohort_comparison": cohorts,
        "transitions": transitions,
        "conclusions": conclusions(strategies, cohorts, transitions),
    }
