"""Tajriba natijasining statistik tahlili: kirish, chiqish va kechiktirilgan testlar bo'yicha tajriba (AI yoqilgan)
va nazorat guruhlari.

1. Tavsifiy statistika (n, M, SD) va Hake normallashtirilgan o'sishi: talaba uchun g = (chiqish − kirish) / (100 − kirish),
   guruh uchun ⟨g⟩ = (M_chiqish − M_kirish) / (100 − M_kirish); daraja: < 0.3 past, 0.3-0.7 o'rta, ≥ 0.7 yuqori.
2. Boshlang'ich tenglik: kirish testida guruhlar farq qilmasligi (p ≥ 0.05) — tajriba xulosasi uchun shart.
3. Guruhlarni solishtirish mezoni shartlarga qarab avtomatik tanlanadi: ikkala guruhda taqsimot normal
   (Shapiro–Uilk p ≥ 0.05) va dispersiyalar teng (Levene, mediana bo'yicha, p ≥ 0.05) — Styudent t;
   normal, lekin dispersiyalar teng emas — Uelch t; normal emas — Mann–Uitni U. Juftlangan (kirish → chiqish):
   farqlar normal — juftlangan t, aks holda Uilkokson.
4. ANCOVA: chiqish ~ guruh + kirish — boshlang'ich farqni hisobga olgan solishtiruv, regressiya chiziqlari
   parallelligi sharti bilan.
5. Statistik quvvat: kuzatilgan effekt bilan erishilgan quvvat va kerakli talabalar soni (o'rta effekt d = 0.5 uchun ham).

Talabalar: kirish va chiqish testlarining ikkalasini topshirganlar (bir nechta test bo'lsa — foizlar o'rtachasi),
faqat tadqiqotga rozi bo'lganlar. Hisob toza Python'da (competence/stats.py), natijalar scipy bilan solishtirilgan.
"""
from collections import defaultdict

from competence.stats import (
    ALPHA,
    achieved_power,
    ancova,
    describe,
    levene,
    mann_whitney,
    paired_t_test,
    required_n_per_group,
    shapiro_wilk,
    student_t_test,
    welch_t_test,
    wilcoxon_signed_rank,
)
from users.consent import consent_required, research_participants
from users.models import User

from .models import Quiz, QuizAttempt
from .services import finalize_if_expired, percent

COHORTS = {"experimental": "Tajriba (AI yoqilgan)", "control": "Nazorat"}
MIN_GROUP = 3
MEDIUM_EFFECT = 0.5
TARGET_POWER = 0.8

TEST_LABELS = {
    "student": "Styudent t-testi",
    "welch": "Uelch t-testi",
    "mann_whitney": "Mann–Uitni U testi",
    "paired_t": "Juftlangan t-testi",
    "wilcoxon": "Uilkokson ishorali ranglar testi",
}


def _r(value, digits=3):
    return None if value is None else round(value, digits)


def _effect_label(kind, value):
    """Koen (1988) bo'yicha effekt hajmi talqini."""
    if value is None:
        return None
    value = abs(value)
    bounds = {"d": (0.2, 0.5, 0.8), "r": (0.1, 0.3, 0.5), "eta2": (0.01, 0.06, 0.14)}[kind]
    if value < bounds[0]:
        return "juda kichik"
    if value < bounds[1]:
        return "kichik"
    if value < bounds[2]:
        return "o'rta"
    return "katta"


def hake_level(g):
    if g is None:
        return None
    return "past" if g < 0.3 else ("o'rta" if g < 0.7 else "yuqori")


def _normality(values):
    result = shapiro_wilk(values)
    if result is None:
        return None
    return {"w": _r(result["w"]), "p": _r(result["p"], 4), "normal": result["p"] >= ALPHA}


def compare_independent(a, b):
    """Ikki mustaqil guruh: shartlar tekshiriladi va mos mezon tanlanadi."""
    if len(a) < MIN_GROUP or len(b) < MIN_GROUP:
        return None
    normal_a, normal_b = _normality(a), _normality(b)
    variances = levene(a, b)
    normal = bool(normal_a and normal_b and normal_a["normal"] and normal_b["normal"])
    equal_var = variances is None or variances["p"] >= ALPHA
    welch = welch_t_test(a, b)
    d = welch["cohens_d"] if welch else None
    if normal and equal_var:
        test, result = "student", student_t_test(a, b)
        reason = "Ikkala guruhda taqsimot normal va dispersiyalar teng."
    elif normal:
        test, result = "welch", welch
        reason = "Taqsimot normal, lekin dispersiyalar teng emas (Levene p < 0.05)."
    else:
        test, result = "mann_whitney", mann_whitney(a, b)
        reason = "Kamida bitta guruhda taqsimot normal emas (Shapiro–Uilk p < 0.05) yoki tekshirib bo'lmadi: parametrsiz mezon."
    if result is None:
        return None
    if test == "mann_whitney":
        effect = {"name": "r", "value": _r(abs(result["z"]) / (len(a) + len(b)) ** 0.5), "kind": "r"}
        statistic = {"name": "U", "value": _r(result["u"], 1), "z": _r(result["z"])}
    else:
        effect = {"name": "d", "value": _r(result["cohens_d"]), "kind": "d"}
        statistic = {"name": "t", "value": _r(result["t"]), "df": _r(result["df"], 1)}
    effect["label"] = _effect_label(effect.pop("kind"), effect["value"])
    return {
        "test": test,
        "label": TEST_LABELS[test],
        "reason": reason,
        "statistic": statistic,
        "p": _r(result["p"], 4),
        "significant": result["p"] < ALPHA,
        "effect": effect,
        "cohens_d": _r(d),
        "assumptions": {
            "normality": {"experimental": normal_a, "control": normal_b},
            "levene": None if variances is None else {"f": _r(variances["f"]), "p": _r(variances["p"], 4), "equal": equal_var},
        },
    }


def compare_paired(before, after):
    if len(before) < MIN_GROUP:
        return None
    diffs = [y - x for x, y in zip(before, after)]
    normality = _normality(diffs)
    if normality and normality["normal"]:
        result = paired_t_test(before, after)
        if result is None:
            return None
        return {
            "test": "paired_t",
            "label": TEST_LABELS["paired_t"],
            "reason": "Farqlar taqsimoti normal.",
            "statistic": {"name": "t", "value": _r(result["t"]), "df": result["df"]},
            "p": _r(result["p"], 4),
            "significant": result["p"] < ALPHA,
            "effect": {"name": "d_z", "value": _r(result["d_z"]), "label": _effect_label("d", result["d_z"])},
            "normality": normality,
        }
    result = wilcoxon_signed_rank(before, after)
    if result is None:
        return None
    return {
        "test": "wilcoxon",
        "label": TEST_LABELS["wilcoxon"],
        "reason": "Farqlar taqsimoti normal emas yoki tekshirib bo'lmadi: parametrsiz mezon.",
        "statistic": {"name": "z", "value": _r(result["z"])},
        "p": _r(result["p"], 4),
        "significant": result["p"] < ALPHA,
        "effect": {"name": "r", "value": _r(result["r"]), "label": _effect_label("r", result["r"])},
        "normality": normality,
    }


def _describe(values):
    result = describe(values)
    return {"n": result["n"], "mean": _r(result["mean"], 2), "sd": _r(result["sd"], 2)}


def student_scores(quizzes, students):
    """{talaba_id: {"pre": %, "post": %, "delayed": %}} — har bir turdagi testlar foizlari o'rtachasi."""
    values = defaultdict(lambda: defaultdict(list))
    attempts = QuizAttempt.objects.filter(quiz__in=quizzes, student__in=students).select_related("quiz")
    for attempt in attempts:
        attempt = finalize_if_expired(attempt)
        if attempt.submitted_at and attempt.max_score:
            values[attempt.student_id][attempt.quiz.kind].append(percent(attempt))
    return {sid: {kind: sum(items) / len(items) for kind, items in kinds.items()} for sid, kinds in values.items()}


def analyse(quizzes, groups):
    """quizzes — ko'rinadigan testlar QuerySet'i, groups — guruhlar. Kirish/chiqish/kechiktirilgan testlar olinadi."""
    groups = list(groups)
    quizzes = quizzes.filter(kind__in=[Quiz.Kind.PRE, Quiz.Kind.POST, Quiz.Kind.DELAYED], groups__in=groups).distinct()
    everyone = User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=groups)
    students = list(research_participants(everyone).select_related("group"))
    scores = student_scores(quizzes, students)
    cohort_of = {student.pk: ("experimental" if student.group.ai_enabled else "control") for student in students}

    completers = {cohort: [] for cohort in COHORTS}
    pre_only = {cohort: 0 for cohort in COHORTS}
    for sid, item in scores.items():
        if "pre" in item and "post" in item:
            completers[cohort_of[sid]].append(item)
        elif "pre" in item:
            pre_only[cohort_of[sid]] += 1

    cohorts = {}
    for cohort, label in COHORTS.items():
        rows = completers[cohort]
        pre = [row["pre"] for row in rows]
        post = [row["post"] for row in rows]
        gains = [(row["post"] - row["pre"]) / (100 - row["pre"]) for row in rows if row["pre"] < 100]
        delayed_rows = [row for row in rows if "delayed" in row]
        pre_stats, post_stats = _describe(pre), _describe(post)
        class_gain = None
        if rows and pre_stats["mean"] is not None and pre_stats["mean"] < 100:
            class_gain = (sum(post) / len(post) - sum(pre) / len(pre)) / (100 - sum(pre) / len(pre))
        cohorts[cohort] = {
            "label": label,
            "students": len(rows),
            "dropped": pre_only[cohort],
            "pre": pre_stats,
            "post": post_stats,
            "delayed": _describe([row["delayed"] for row in delayed_rows]),
            "gain": {
                "class": _r(class_gain),
                "level": hake_level(class_gain),
                "individual": _describe(gains),
            },
            "pre_post": compare_paired(pre, post),
            "post_delayed": compare_paired([row["post"] for row in delayed_rows], [row["delayed"] for row in delayed_rows]),
        }

    def column(cohort, key):
        if key == "gain":
            return [(row["post"] - row["pre"]) / (100 - row["pre"]) for row in completers[cohort] if row["pre"] < 100]
        return [row[key] for row in completers[cohort] if key in row]

    comparisons = {key: compare_independent(column("experimental", key), column("control", key)) for key in ("pre", "post", "gain", "delayed")}
    baseline = comparisons["pre"]

    covariance = ancova({cohort: [(row["pre"], row["post"]) for row in completers[cohort]] for cohort in COHORTS})
    ancova_result = None
    if covariance:
        slopes = covariance["slopes_homogeneity"]
        ancova_result = {
            "f": _r(covariance["f"]),
            "df1": covariance["df1"],
            "df2": covariance["df2"],
            "p": _r(covariance["p"], 4),
            "significant": covariance["p"] < ALPHA,
            "partial_eta2": _r(covariance["partial_eta2"]),
            "effect_label": _effect_label("eta2", covariance["partial_eta2"]),
            "adjusted_means": {cohort: _r(value, 2) for cohort, value in covariance["adjusted_means"].items()},
            "slopes": None if slopes is None else {"f": _r(slopes["f"]), "p": _r(slopes["p"], 4), "parallel": slopes["p"] >= ALPHA},
        }

    n1, n2 = len(completers["experimental"]), len(completers["control"])
    observed_d = comparisons["post"]["cohens_d"] if comparisons["post"] else None
    power = {
        "observed_d": observed_d,
        "achieved": _r(achieved_power(observed_d, n1, n2)) if observed_d else None,
        "required_per_group_observed": required_n_per_group(observed_d, power=TARGET_POWER) if observed_d else None,
        "required_per_group_medium": required_n_per_group(MEDIUM_EFFECT, power=TARGET_POWER),
        "target": TARGET_POWER,
        "alpha": ALPHA,
        "approximate": True,
    }

    return {
        "consent_required": consent_required(),
        "students": len(students),
        "excluded_no_consent": everyone.count() - len(students),
        "quizzes": {kind: quizzes.filter(kind=kind).count() for kind in ("pre", "post", "delayed")},
        "alpha": ALPHA,
        "cohorts": cohorts,
        "baseline": baseline,
        "comparisons": {key: comparisons[key] for key in ("post", "gain", "delayed")},
        "ancova": ancova_result,
        "power": power,
        "conclusions": conclusions(cohorts, baseline, comparisons, ancova_result, power, n1, n2),
    }


def _p_text(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def conclusions(cohorts, baseline, comparisons, ancova_result, power, n1, n2):
    """Dissertatsiya matniga mos qisqa xulosalar (o'zbekcha)."""
    lines = []
    if min(n1, n2) < MIN_GROUP:
        return ["Har bir guruhda kamida 3 ta talaba kirish va chiqish testini topshirgan bo'lishi kerak."]
    if baseline:
        if baseline["significant"]:
            lines.append(
                f"Diqqat: tajriba boshida guruhlar kirish testi bo'yicha farq qilgan ({baseline['label']}, {_p_text(baseline['p'])}). "
                "Asosiy xulosa uchun ANCOVA natijasiga tayaning."
            )
        else:
            lines.append(f"Tajriba boshida guruhlar kirish testi bo'yicha teng bo'lgan ({baseline['label']}, {_p_text(baseline['p'])}).")
    post = comparisons["post"]
    if post:
        exp, ctrl = cohorts["experimental"]["post"]["mean"], cohorts["control"]["post"]["mean"]
        verdict = "statistik ahamiyatli farq bor" if post["significant"] else "statistik ahamiyatli farq yo'q"
        lines.append(
            f"Chiqish testida tajriba guruhi o'rtachasi {exp}%, nazorat guruhiniki {ctrl}%: {verdict} "
            f"({post['label']}, {_p_text(post['p'])}, {post['effect']['name']} = {post['effect']['value']} — {post['effect']['label']} effekt)."
        )
    gain_exp, gain_ctrl = cohorts["experimental"]["gain"], cohorts["control"]["gain"]
    if gain_exp["class"] is not None and gain_ctrl["class"] is not None:
        lines.append(
            f"Hake o'sishi: tajriba guruhida ⟨g⟩ = {gain_exp['class']} ({gain_exp['level']}), "
            f"nazorat guruhida ⟨g⟩ = {gain_ctrl['class']} ({gain_ctrl['level']})."
        )
    if ancova_result:
        verdict = "ahamiyatli" if ancova_result["significant"] else "ahamiyatli emas"
        lines.append(
            f"Kirish testi natijasini hisobga olganda (ANCOVA) guruhlar farqi {verdict}: F({ancova_result['df1']}, {ancova_result['df2']}) = "
            f"{ancova_result['f']}, {_p_text(ancova_result['p'])}, qisman η² = {ancova_result['partial_eta2']} ({ancova_result['effect_label']})."
        )
        if ancova_result["slopes"] and not ancova_result["slopes"]["parallel"]:
            lines.append("ANCOVA sharti buzilgan (regressiya chiziqlari parallel emas): natijani ehtiyotkorlik bilan talqin qiling.")
    if power["achieved"] is not None:
        if power["achieved"] < power["target"]:
            lines.append(
                f"Statistik quvvat past ({round(100 * power['achieved'])}%): kuzatilgan effektni ishonchli aniqlash uchun har bir "
                f"guruhda taxminan {power['required_per_group_observed']} ta talaba kerak (hozir {n1} va {n2})."
            )
        else:
            lines.append(f"Statistik quvvat yetarli ({round(100 * power['achieved'])}%).")
    return lines
