"""Aralashuvning bajarilishi (treatment fidelity): "AI yoqilgan" guruh AI dan haqiqatda foydalanganmi.

Asosiy tahlil guruhning shartiga qaraydi (intention-to-treat), lekin AI yoqilgan bo'lsa ham talaba undan foydalanmasligi
mumkin: unda "effekt yo'q" degan xulosa AI haqida emas, foydalanilmagani haqida bo'ladi.

1. Doza: kirish testi topshirilgandan chiqish testi topshirilgunicha platformadagi AI murojaatlari soni — maslahat darajalari
   (LabAttempt), boshqa AI so'rovlari (AIAction) va chat savollari (ChatMessage). AI baholashi kirmaydi: uni talaba so'ramaydi.
   Matnlar o'qilmaydi va natijaga chiqmaydi, faqat sonlar.
2. Qamrov: tajriba guruhida kamida bir marta foydalanganlar ulushi; FIDELITY_TARGET dan past bo'lsa, ogohlantiriladi.
3. Shart buzilishi: nazorat guruhida AI murojaati borlar va urinish paytidagi AI holati (LabAttempt.ai_enabled) hozirgi guruh
   shartidan farq qiladiganlar (sozlama o'zgartirilgan yoki talaba boshqa guruhga o'tgan).
4. Doza va natija (faqat tajriba guruhi): doza va kirish testi ta'siri olib tashlangan chiqish natijasi orasidagi Spirmen ρ.
   Bu kuzatuv natijasi, sabab emas: qiynalgan talaba ko'proq yordam so'raydi, kuchli talaba esa kam.
5. Sezgirlik (per-protocol): foydalanmaganlar (tajriba) va AI ga kirganlar (nazorat) chiqarilgandagi ANCOVA. Guruhlar tengligi
   buziladi, shuning uchun asosiy xulosa o'rnini bosmaydi.
"""
from collections import defaultdict
from statistics import median

from competence.stats import ALPHA, linear_residuals, spearman
from labs.models import LabAttempt
from labs.research import ai_events

from .models import Quiz, QuizAttempt

# Yuqori bajarilish chegarasi (Borrelli, 2011: ≥ 80%)
FIDELITY_TARGET = 0.8
MIN_DOSE_STUDENTS = 5
SOURCES = ("hints", "actions", "chat")


def _r(value, digits=3):
    return None if value is None else round(value, digits)


def exposure_windows(quizzes, student_ids):
    """{talaba_id: (birinchi kirish testi, oxirgi chiqish testi)} — topshirilgan vaqtlar; tartibi buzilganlar kirmaydi."""
    starts, ends = {}, {}
    rows = QuizAttempt.objects.filter(
        quiz__in=quizzes, student__in=student_ids, submitted_at__isnull=False
    ).values_list("student_id", "quiz__kind", "submitted_at")
    for student_id, kind, moment in rows:
        if kind == Quiz.Kind.PRE:
            starts[student_id] = min(moment, starts.get(student_id, moment))
        elif kind == Quiz.Kind.POST:
            ends[student_id] = max(moment, ends.get(student_id, moment))
    return {sid: (starts[sid], ends[sid]) for sid in starts if sid in ends and starts[sid] < ends[sid]}


def ai_usage(windows):
    """{talaba_id: {manba: son}} — faqat o'z oynasi ichidagi AI murojaatlari."""
    usage = {sid: dict.fromkeys(SOURCES, 0) for sid in windows}
    for student_id, moment, source, _, amount in ai_events(windows):
        start, end = windows[student_id]
        if start <= moment <= end:
            usage[student_id][source] += amount
    return usage


def changed_condition(windows, cohort_of):
    """Oynadagi kamida bitta urinishida AI holati hozirgi guruh shartiga mos kelmagan talabalar."""
    changed = set()
    rows = LabAttempt.objects.filter(student__in=windows).values_list("student_id", "created_at", "ai_enabled")
    for student_id, moment, enabled in rows:
        start, end = windows[student_id]
        if start <= moment <= end and enabled != (cohort_of[student_id] == "experimental"):
            changed.add(student_id)
    return changed


def analyse(quizzes, completers):
    """quizzes — kirish/chiqish testlari, completers — {guruh: [{"student", "pre", "post"}, ...]} (experiment.py dan)."""
    from .experiment import COHORTS, _describe, sensitivity_ancova

    cohort_of = {row["student"]: cohort for cohort, rows in completers.items() for row in rows}
    windows = exposure_windows(quizzes, list(cohort_of))
    usage = ai_usage(windows)
    changed = changed_condition(windows, cohort_of)
    dose = {sid: sum(sources.values()) for sid, sources in usage.items()}

    cohorts = {}
    for cohort, label in COHORTS.items():
        rows = [row for row in completers[cohort] if row["student"] in windows]
        doses = [dose[row["student"]] for row in rows]
        users = sum(1 for value in doses if value)
        cohorts[cohort] = {
            "label": label,
            "students": len(rows),
            "no_window": len(completers[cohort]) - len(rows),
            "users": users,
            "uptake": _r(users / len(rows)) if rows else None,
            "dose": {**_describe(doses), "median": median(doses) if doses else None},
            "sources": {source: sum(usage[row["student"]][source] for row in rows) for source in SOURCES},
            "changed_condition": sum(1 for row in rows if row["student"] in changed),
        }

    kept = {
        "experimental": [(row["pre"], row["post"]) for row in completers["experimental"] if dose.get(row["student"])],
        "control": [(row["pre"], row["post"]) for row in completers["control"] if dose.get(row["student"]) == 0],
    }
    excluded = sum(map(len, completers.values())) - sum(map(len, kept.values()))
    return {
        "target": FIDELITY_TARGET,
        "cohorts": cohorts,
        "dose_response": dose_response([row for row in completers["experimental"] if row["student"] in windows], dose),
        "per_protocol": sensitivity_ancova(kept, excluded),
    }


def dose_response(rows, dose):
    """Tajriba guruhi: doza va kirish testi ta'siri olib tashlangan chiqish natijasi (Spirmen ρ, Fisher z oralig'i)."""
    if len(rows) < MIN_DOSE_STUDENTS:
        return None
    residuals = linear_residuals([row["pre"] for row in rows], [row["post"] for row in rows])
    result = spearman([dose[row["student"]] for row in rows], residuals)
    if result is None:
        return None
    return {
        "n": result["n"],
        "rho": _r(result["rho"]),
        "ci": None if result["ci"] is None else [_r(result["ci"][0]), _r(result["ci"][1])],
        "p": _r(result["p"], 4),
        "significant": result["p"] < ALPHA,
    }


def conclusions(result):
    from .experiment import _ci_text, _p_text

    exp, ctrl = result["cohorts"]["experimental"], result["cohorts"]["control"]
    lines = []
    if exp["students"]:
        lines.append(
            f"Aralashuvning bajarilishi: tajriba guruhidagi {exp['students']} ta talabadan {exp['users']} tasi "
            f"({round(100 * exp['uptake'])}%) kirish va chiqish testlari orasida platformadagi AI dan foydalangan "
            f"(mediana {exp['dose']['median']:g} ta murojaat)."
        )
        if exp["uptake"] < result["target"]:
            lines.append(
                f"Diqqat: AI dan foydalanganlar {round(100 * result['target'])}% dan kam — \"AI yoqilgan\" guruh AI ni to'liq "
                "ishlatmagan, shuning uchun asosiy tahlil AI imkoniyati effektini o'lchaydi, AI ning o'zi effektini kam ko'rsatishi mumkin."
            )
    if ctrl["users"]:
        lines.append(
            f"Shart buzilishi: nazorat guruhida {ctrl['users']} ta talaba kirish va chiqish testlari orasida platformadagi AI ga "
            "murojaat qilgan. Guruh sozlamalari tajriba davomida o'zgarmaganini tekshiring."
        )
    changed = exp["changed_condition"] + ctrl["changed_condition"]
    if changed:
        lines.append(
            f"Shart buzilishi: {changed} ta talabaning urinishlarida AI holati hozirgi guruh shartiga mos emas (AI sozlamasi "
            "o'zgartirilgan yoki talaba boshqa guruhga o'tgan). Ular noto'g'ri guruhda hisoblangan bo'lishi mumkin."
        )
    response = result["dose_response"]
    if response:
        interval = f", {_ci_text(response['ci'])}" if response["ci"] else ""
        verdict = "ahamiyatli" if response["significant"] else "ahamiyatli emas"
        lines.append(
            f"Doza va natija: tajriba guruhida AI murojaatlari soni va kirish testini hisobga olgan chiqish natijasi orasida "
            f"Spirmen ρ = {response['rho']}{interval}, {_p_text(response['p'])} — {verdict}. Bu kuzatuv natijasi, sabab emas: "
            "talabalar yordamni o'zlari tanlaydi, qiynalganlar ko'proq so'raydi."
        )
    protocol = result["per_protocol"]
    if protocol:
        verdict = "ahamiyatli" if protocol["significant"] else "ahamiyatli emas"
        lines.append(
            f"Sezgirlik tahlili (per-protocol): shartga amal qilmagan {protocol['excluded']} ta talaba chiqarilganda ANCOVA "
            f"F({protocol['df1']}, {protocol['df2']}) = {protocol['f']}, {_p_text(protocol['p'])} — {verdict}. Guruhlar tengligi "
            "buziladi, asosiy xulosa o'rnini bosmaydi."
        )
    return lines
