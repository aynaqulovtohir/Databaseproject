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
6. Asosiy gipoteza oldindan belgilangan (PRIMARY_OUTCOME): ANCOVA bo'yicha guruh effekti, α = 0.05 tuzatishsiz.
   Qolgan solishtiruvlar (chiqish testi, Hake o'sishi, kechiktirilgan test) — ikkilamchi, ularga Xolm tuzatishi qo'llanadi.
7. Klasterlash: AI butun akademik guruhga yoqiladi, ya'ni dizayn — klaster kvazi-tajriba. ANCOVA qoldiqlari bo'yicha
   guruhlararo ICC(1), dizayn effekti va samarali talabalar soni hisoblanadi; har bir shartda bittadan guruh bo'lsa,
   guruh effektini AI effektidan ajratib bo'lmasligi haqida ogohlantiriladi.
8. Parallel variantlar (forms.py): A va B ekvivalentligi (TOST), ishonchliligi va bir xil variant olganlar.
9. Nazorat guruhining "ifloslanishi": yakuniy so'rovnomadagi tashqi AI vositalari haqidagi savollar (survey_bank.py)
   bo'yicha guruhlar solishtiriladi va sezgirlik tahlili — tashqi AI dan ko'p foydalanganlar (o'rtacha ≥ 4)
   chiqarilgandagi ANCOVA.
10. Ma'lumot sifati: kirish testida 100% olganlar (Hake g aniqlanmaydi), chiqish testidagi shift effekti (> 15% talaba
   maksimal ball olgan) va kechiktirilgan testni topshirmaganlar alohida ko'rsatiladi.
11. Tashlab ketish (attrition, CONSORT): kirish → chiqish va chiqish → kechiktirilgan test bosqichlarida guruhlar bo'yicha
   ulush, umumiy darajasi ("5 va 20" qoidasi), guruhlar farqi (χ², kutilgan sonlar kichik bo'lsa — Fisherning aniq testi)
   va tashlab ketganlarning oldingi testda qolganlardan farqi.

Talabalar: kirish va chiqish testlarining ikkalasini topshirganlar (bir nechta test bo'lsa — foizlar o'rtachasi),
faqat tadqiqotga rozi bo'lganlar. Hisob toza Python'da (competence/stats.py), natijalar scipy bilan solishtirilgan.
"""
from collections import defaultdict

from competence.stats import (
    ALPHA,
    achieved_power,
    ancova,
    chi_square,
    describe,
    fisher_exact,
    holm,
    icc_oneway,
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

from . import forms as parallel_forms
from .models import Question, Quiz, QuizAttempt
from .services import finalize_if_expired, likert_value, percent
from .survey_bank import EXTERNAL_AI_TEXTS

COHORTS = {"experimental": "Tajriba (AI yoqilgan)", "control": "Nazorat"}
MIN_GROUP = 3
MEDIUM_EFFECT = 0.5
TARGET_POWER = 0.8
# Asosiy (oldindan belgilangan) natija ko'rsatkichi: tajriba boshlanishidan oldin qayd etiladi va o'zgartirilmaydi
PRIMARY_OUTCOME = "ancova"
PRIMARY_LABEL = "Chiqish testi, kirish testini hisobga olgan holda (ANCOVA: chiqish ~ guruh + kirish)"
SECONDARY = ("post", "gain", "delayed")
# Tashqi AI dan "ko'p foydalangan": shu savollar o'rtachasi (1-5) shu qiymatdan kichik emas
HEAVY_EXTERNAL = 4
# Shift effekti: maksimal ball olganlar ulushi shu chegaradan oshsa, test guruhlarni farqlay olmasligi mumkin
CEILING_SHARE = 0.15
# Tashlab ketish ulushi chegaralari (Shulz va Grayms, 2002, "5 va 20" qoidasi)
ATTRITION_LOW, ATTRITION_HIGH = 0.05, 0.20

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


def apply_holm(tests):
    """Ikkilamchi solishtiruvlarga Xolm tuzatishi: har biriga p_holm va significant_holm qo'shiladi."""
    present = [test for test in tests if test]
    adjusted = holm([test["p"] for test in present])
    for test, p in zip(present, adjusted):
        test["p_holm"] = _r(p, 4)
        test["significant_holm"] = p < ALPHA


def cluster_analysis(completers, covariance):
    """Akademik guruhlar (klasterlar) ta'siri: ANCOVA qoldiqlari bo'yicha ICC(1), dizayn effekti, samarali n.

    Qoldiq = chiqish − (b₀ + b₁·tajriba + b₂·kirish): AI va kirish testi ta'siri olib tashlangandan keyin
    bir guruh talabalari bir-biriga qanchalik o'xshashligi. Har bir shartda bittadan guruh bo'lsa, qoldiqlarning
    guruh o'rtachasi 0 ga teng bo'ladi va ICC ni baholab bo'lmaydi.
    """
    groups = {cohort: len({row["group"] for row in rows}) for cohort, rows in completers.items()}
    result = {"groups": groups, "confounded": min(groups.values()) <= 1, "icc": None}
    if covariance is None or result["confounded"]:
        return result
    b0, b1, b2 = covariance["beta"]
    residuals = defaultdict(list)
    for cohort, rows in completers.items():
        flag = 1.0 if cohort == "experimental" else 0.0
        for row in rows:
            residuals[row["group"]].append(row["post"] - (b0 + b1 * flag + b2 * row["pre"]))
    icc = icc_oneway(list(residuals.values()))
    if icc:
        result["icc"] = {
            "value": _r(icc["icc"]),
            "f": _r(icc["f"]),
            "p": _r(icc["p"], 4),
            "clusters": icc["clusters"],
            "mean_size": _r(icc["mean_size"], 1),
            "design_effect": _r(icc["design_effect"], 2),
            "effective_n": _r(icc["effective_n"], 1),
        }
    return result


def external_usage(surveys, students):
    """{talaba_id: tashqi AI savollari o'rtachasi (1-5)} — yakuniy so'rovnoma(lar) bo'yicha."""
    values = defaultdict(list)
    attempts = QuizAttempt.objects.filter(quiz__in=surveys, student__in=students, submitted_at__isnull=False)
    questions = defaultdict(list)
    for question in Question.objects.filter(quiz__in=surveys, text__in=EXTERNAL_AI_TEXTS).prefetch_related("choices"):
        questions[question.quiz_id].append(question)
    for attempt in attempts:
        for question in questions.get(attempt.quiz_id, []):
            value = likert_value(question, attempt.answers.get(str(question.pk), []))
            if value is not None:
                values[attempt.student_id].append(value)
    return {sid: sum(items) / len(items) for sid, items in values.items()}


def external_ai(surveys, students, cohort_of, completers):
    """Tashqi AI dan foydalanish: guruhlar bo'yicha o'rtacha, ko'p foydalanganlar ulushi va sezgirlik tahlili."""
    usage = external_usage(surveys, students)
    result = {"threshold": HEAVY_EXTERNAL, "answered": len(usage), "cohorts": {}, "comparison": None, "sensitivity": None}
    if not usage:
        return result
    by_cohort = defaultdict(list)
    for sid, value in usage.items():
        by_cohort[cohort_of[sid]].append(value)
    for cohort in COHORTS:
        values = by_cohort[cohort]
        heavy = sum(1 for value in values if value >= HEAVY_EXTERNAL)
        result["cohorts"][cohort] = {**_describe(values), "heavy": heavy, "heavy_share": _r(heavy / len(values)) if values else None}
    result["comparison"] = compare_independent(by_cohort["experimental"], by_cohort["control"])
    # Sezgirlik: tashqi AI dan ko'p foydalanganlar chiqarilgandagi ANCOVA (asosiy xulosa o'zgarmasligi kerak)
    kept = {
        cohort: [(row["pre"], row["post"]) for row in rows if usage.get(row["student"], 0) < HEAVY_EXTERNAL]
        for cohort, rows in completers.items()
    }
    excluded = sum(len(rows) for rows in completers.values()) - sum(len(rows) for rows in kept.values())
    if excluded and min(len(rows) for rows in kept.values()) >= MIN_GROUP:
        covariance = ancova(kept)
        if covariance:
            result["sensitivity"] = {
                "excluded": excluded,
                "f": _r(covariance["f"]),
                "df1": covariance["df1"],
                "df2": covariance["df2"],
                "p": _r(covariance["p"], 4),
                "significant": covariance["p"] < ALPHA,
                "partial_eta2": _r(covariance["partial_eta2"]),
            }
    return result


def external_conclusions(result):
    if not result["answered"]:
        return []
    control = result["cohorts"].get("control") or {}
    lines = []
    if control.get("n"):
        lines.append(
            f"Tashqi AI vositalari: nazorat guruhida {control['heavy']} ta talaba (ulushi {control['heavy_share']}) ulardan ko'p "
            f"foydalanganini bildirgan (o'rtacha ≥ {result['threshold']}) — bu AI effektini kamaytirib ko'rsatishi mumkin."
        )
    sensitivity = result["sensitivity"]
    if sensitivity:
        verdict = "ahamiyatli" if sensitivity["significant"] else "ahamiyatli emas"
        lines.append(
            f"Sezgirlik tahlili: tashqi AI dan ko'p foydalangan {sensitivity['excluded']} ta talaba chiqarilganda ANCOVA "
            f"F({sensitivity['df1']}, {sensitivity['df2']}) = {sensitivity['f']}, {_p_text(sensitivity['p'])} — {verdict}."
        )
    return lines


def attrition_stage(started, kept_key, score_key):
    """Bir bosqichdagi tashlab ketish: started — {guruh: [baholar]} (bosqichni boshlaganlar), kept_key — keyingi test
    turi (shu kalit bo'lmasa, talaba tashlab ketgan), score_key — tashlab ketganlar va qolganlar solishtiriladigan test."""
    cohorts, table, lost_scores, kept_scores = {}, [], [], []
    for cohort, label in COHORTS.items():
        rows = started[cohort]
        lost = [row for row in rows if kept_key not in row]
        cohorts[cohort] = {"label": label, "started": len(rows), "lost": len(lost), "rate": _r(len(lost) / len(rows)) if rows else None}
        table.append([len(lost), len(rows) - len(lost)])
        lost_scores += [row[score_key] for row in lost]
        kept_scores += [row[score_key] for row in rows if kept_key in row]
    started_total, lost_total = sum(map(sum, table)), sum(row[0] for row in table)
    result = {
        "cohorts": cohorts,
        "overall": _r(lost_total / started_total) if started_total else None,
        "differential": None,
        "level": None,
        "test": None,
        "baseline": None,
    }
    if not started_total:
        return result
    overall = lost_total / started_total
    # Shulz va Grayms (2002) "5 va 20" qoidasi: < 5% — siljish xavfi kam, > 20% — jiddiy xavf
    result["level"] = "past" if overall < ATTRITION_LOW else ("o'rta" if overall <= ATTRITION_HIGH else "yuqori")
    exp_rate, ctrl_rate = cohorts["experimental"]["rate"], cohorts["control"]["rate"]
    if exp_rate is not None and ctrl_rate is not None:
        result["differential"] = _r(table[0][0] / sum(table[0]) - table[1][0] / sum(table[1]))
    if lost_total and all(sum(row) for row in table):
        chi = chi_square(table)
        if chi and chi["reliable"]:
            result["test"] = {"name": "chi2", "label": "Pirson χ²", "chi2": _r(chi["chi2"]), "df": chi["df"], "p": _r(chi["p"], 4)}
        else:
            # Kutilgan sonlar kichik (yoki bitta guruhda hech kim tashlab ketmagan) — Fisherning aniq testi
            fisher = fisher_exact(table)
            if fisher:
                result["test"] = {"name": "fisher", "label": "Fisherning aniq testi", "p": _r(fisher["p"], 4)}
        if result["test"]:
            result["test"]["significant"] = result["test"]["p"] < ALPHA
    # Tashlab ketganlar boshida qolganlardan farq qilganmi (farq qilsa, qolganlar tanlanmasi siljigan)
    result["baseline"] = compare_independent(lost_scores, kept_scores)
    return result


def attrition_analysis(scores, cohort_of, has_delayed):
    """Tashlab ketish: kirish → chiqish (kirish testi bo'yicha) va chiqish → kechiktirilgan (chiqish testi bo'yicha)."""
    started = {cohort: [] for cohort in COHORTS}
    for sid, item in scores.items():
        if "pre" in item:
            started[cohort_of[sid]].append(item)
    result = {"post": attrition_stage(started, "post", "pre"), "delayed": None}
    if has_delayed:
        completed = {cohort: [row for row in rows if "post" in row] for cohort, rows in started.items()}
        result["delayed"] = attrition_stage(completed, "delayed", "post")
    return result


def _attrition_lines(stage, title, score_label):
    if stage is None or not stage["overall"]:
        return []
    exp, ctrl = stage["cohorts"]["experimental"], stage["cohorts"]["control"]
    lines = [
        f"{title}: tajriba guruhida {exp['lost']} ta talaba ({_share(exp['rate'])}), nazorat guruhida {ctrl['lost']} ta "
        f"({_share(ctrl['rate'])}) tashlab ketgan; umumiy {_share(stage['overall'])} — siljish xavfi {stage['level']}."
    ]
    test = stage["test"]
    if test and test["significant"]:
        lines.append(
            f"Diqqat: guruhlar tashlab ketish ulushi bo'yicha farq qiladi ({test['label']}, {_p_text(test['p'])}) — "
            "differensial tashlab ketish, guruhlar endi teng emas bo'lishi mumkin. Sezgirlik tahlili (masalan, ko'p "
            "imputatsiya yoki chegaraviy baholar) bilan tekshiring."
        )
    baseline = stage["baseline"]
    if baseline and baseline["significant"]:
        lines.append(
            f"Tashlab ketganlar {score_label} qolganlardan farq qilgan ({baseline['label']}, {_p_text(baseline['p'])}): "
            "natijalar faqat oxirigacha qatnashganlarga tegishli, ularni butun guruhga umumlashtirishda ehtiyot bo'ling."
        )
    return lines


def attrition_conclusions(result):
    return _attrition_lines(result["post"], "Tashlab ketish (kirish → chiqish)", "kirish testida") + _attrition_lines(
        result["delayed"], "Kechiktirilgan testgacha tashlab ketish", "chiqish testida"
    )


def _share(value):
    return f"{round(100 * value)}%"


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
    surveys = quizzes.filter(kind=Quiz.Kind.SURVEY, groups__in=groups).distinct()
    quizzes = quizzes.filter(kind__in=[Quiz.Kind.PRE, Quiz.Kind.POST, Quiz.Kind.DELAYED], groups__in=groups).distinct()
    everyone = User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=groups)
    students = list(research_participants(everyone).select_related("group"))
    scores = student_scores(quizzes, students)
    cohort_of = {student.pk: ("experimental" if student.group.ai_enabled else "control") for student in students}
    group_of = {student.pk: student.group_id for student in students}

    completers = {cohort: [] for cohort in COHORTS}
    pre_only = {cohort: 0 for cohort in COHORTS}
    for sid, item in scores.items():
        if "pre" in item and "post" in item:
            completers[cohort_of[sid]].append({**item, "group": group_of[sid], "student": sid})
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
        at_ceiling = sum(1 for value in post if value >= 100)
        cohorts[cohort] = {
            "label": label,
            "students": len(rows),
            "dropped": pre_only[cohort],
            "groups": len({row["group"] for row in rows}),
            "pre": pre_stats,
            "post": post_stats,
            "delayed": _describe([row["delayed"] for row in delayed_rows]),
            "delayed_missing": len(rows) - len(delayed_rows),
            "gain": {
                "class": _r(class_gain),
                "level": hake_level(class_gain),
                "individual": _describe(gains),
                # Kirish testida 100% olganlarda g = (chiqish − 100) / 0 aniqlanmaydi: ular individual g dan chiqariladi
                "excluded_full_pre": len(rows) - len(gains),
            },
            "ceiling": {
                "students": at_ceiling,
                "share": _r(at_ceiling / len(rows)) if rows else None,
                "warning": bool(rows) and at_ceiling / len(rows) > CEILING_SHARE,
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
    apply_holm([comparisons[key] for key in SECONDARY])

    covariance = ancova({cohort: [(row["pre"], row["post"]) for row in completers[cohort]] for cohort in COHORTS})
    ancova_result = None
    if covariance:
        slopes = covariance["slopes_homogeneity"]
        ancova_result = {
            "primary": PRIMARY_OUTCOME == "ancova",
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
    clustering = cluster_analysis(completers, covariance)
    forms = parallel_forms.analyse(quizzes, students)
    external = external_ai(surveys, students, cohort_of, completers)
    attrition = attrition_analysis(scores, cohort_of, quizzes.filter(kind=Quiz.Kind.DELAYED).exists())

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
        "primary": {"outcome": PRIMARY_OUTCOME, "label": PRIMARY_LABEL},
        "cohorts": cohorts,
        "baseline": baseline,
        "comparisons": {key: comparisons[key] for key in ("post", "gain", "delayed")},
        "ancova": ancova_result,
        "power": power,
        "clustering": clustering,
        "forms": forms,
        "external_ai": external,
        "attrition": attrition,
        "conclusions": conclusions(cohorts, baseline, comparisons, ancova_result, power, n1, n2, clustering)
        + attrition_conclusions(attrition)
        + parallel_forms.conclusions(forms)
        + external_conclusions(external),
    }


def _p_text(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _secondary_text(test):
    """Ikkilamchi natija: xom p va Xolm bo'yicha tuzatilgan p."""
    if "p_holm" not in test:
        return _p_text(test["p"])
    return f"{_p_text(test['p'])}, Xolm bo'yicha p = {test['p_holm']:.3f}"


def conclusions(cohorts, baseline, comparisons, ancova_result, power, n1, n2, clustering=None):
    """Dissertatsiya matniga mos qisqa xulosalar (o'zbekcha). Avval asosiy gipoteza, keyin ikkilamchi natijalar."""
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
    if ancova_result:
        verdict = "ahamiyatli" if ancova_result["significant"] else "ahamiyatli emas"
        lines.append(
            f"Asosiy gipoteza (oldindan belgilangan): kirish testi natijasini hisobga olganda (ANCOVA) guruhlar farqi {verdict}: "
            f"F({ancova_result['df1']}, {ancova_result['df2']}) = {ancova_result['f']}, {_p_text(ancova_result['p'])}, "
            f"qisman η² = {ancova_result['partial_eta2']} ({ancova_result['effect_label']})."
        )
        if ancova_result["slopes"] and not ancova_result["slopes"]["parallel"]:
            lines.append("ANCOVA sharti buzilgan (regressiya chiziqlari parallel emas): natijani ehtiyotkorlik bilan talqin qiling.")
    post = comparisons["post"]
    if post:
        exp, ctrl = cohorts["experimental"]["post"]["mean"], cohorts["control"]["post"]["mean"]
        significant = post.get("significant_holm", post["significant"])
        verdict = "statistik ahamiyatli farq bor" if significant else "statistik ahamiyatli farq yo'q"
        lines.append(
            f"Ikkilamchi: chiqish testida tajriba guruhi o'rtachasi {exp}%, nazorat guruhiniki {ctrl}%: {verdict} "
            f"({post['label']}, {_secondary_text(post)}, {post['effect']['name']} = {post['effect']['value']} — {post['effect']['label']} effekt)."
        )
    gain_exp, gain_ctrl = cohorts["experimental"]["gain"], cohorts["control"]["gain"]
    if gain_exp["class"] is not None and gain_ctrl["class"] is not None:
        lines.append(
            f"Hake o'sishi: tajriba guruhida ⟨g⟩ = {gain_exp['class']} ({gain_exp['level']}), "
            f"nazorat guruhida ⟨g⟩ = {gain_ctrl['class']} ({gain_ctrl['level']})."
        )
    full_pre = sum(cohorts[key]["gain"]["excluded_full_pre"] for key in COHORTS)
    if full_pre:
        lines.append(f"Kirish testida 100% olgan {full_pre} ta talaba individual Hake o'sishidan chiqarildi (g aniqlanmaydi).")
    ceiling = [cohorts[key]["label"] for key in COHORTS if cohorts[key]["ceiling"]["warning"]]
    if ceiling:
        lines.append(
            f"Shift effekti: {', '.join(ceiling)} guruhida chiqish testida maksimal ball olganlar 15% dan ko'p — test "
            "kuchli talabalarni farqlay olmaydi, guruhlar farqi kam ko'rsatilishi mumkin."
        )
    if clustering:
        if clustering["confounded"]:
            lines.append(
                "Dizayn cheklovi: kamida bitta shartda faqat bitta akademik guruh bor — AI ta'sirini guruh (o'qituvchi, jadval, "
                "muhit) ta'siridan statistik ajratib bo'lmaydi. Xulosani kvazi-tajriba sifatida bering yoki har bir shartga "
                "ikki va undan ko'p guruh oling."
            )
        elif clustering["icc"]:
            icc = clustering["icc"]
            lines.append(
                f"Klasterlash: guruhlararo ICC = {icc['value']}, dizayn effekti {icc['design_effect']}, samarali talabalar soni "
                f"≈ {icc['effective_n']}. ICC 0.05 dan katta bo'lsa, ko'p darajali model (guruh — tasodifiy effekt) bilan "
                "tekshiring (qayta hisoblash skripti)."
            )
    if power["achieved"] is not None:
        if power["achieved"] < power["target"]:
            lines.append(
                f"Statistik quvvat past ({round(100 * power['achieved'])}%): kuzatilgan effektni ishonchli aniqlash uchun har bir "
                f"guruhda taxminan {power['required_per_group_observed']} ta talaba kerak (hozir {n1} va {n2})."
            )
        else:
            lines.append(f"Statistik quvvat yetarli ({round(100 * power['achieved'])}%).")
    return lines
