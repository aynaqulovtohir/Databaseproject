"""Kompetentlik ko'rsatkichlari, komponent ballari va darajalarini hisoblash.

Har bir ko'rsatkich talaba uchun 0-100 oralig'idagi qiymat beradi yoki None (bu kesimda o'lchanmagan:
test topshirilmagan, laboratoriya berilmagan va h.k.). Komponent bali — o'lchangan ko'rsatkichlarning
vaznli o'rtachasi; ko'rsatkichi o'lchanmagan komponent "o'lchanmagan" bo'ladi (nol emas), shunda topshirmagan
talaba past daraja sifatida sanalmaydi.

Kesimlar: tajriba boshida (initial), oxirida (final) va bir necha hafta keyin (delayed — kechiktirilgan test,
bilim saqlanishi). Test va so'rovnoma ko'rsatkichlari har bir kesimda o'ziga bog'langan testlardan olinadi;
laboratoriya va baho ko'rsatkichlari o'quv jarayonida yig'iladi, shuning uchun faqat tajriba oxirida o'lchanadi.

LLM ishlatilmaydi: hisob tez va tushuntirib berish mumkin.
"""
import math
from collections import defaultdict

from django.db.models import Prefetch

from grading.models import Grade
from labs import mastery
from labs.calibration import calibration
from labs.interview import coverage
from labs.models import InterviewMessage, Lab, LabAttempt, PeerReview
from labs.peer_review import accuracy as peer_accuracy
from quizzes.models import Question, QuizAttempt
from quizzes.services import finalize_if_expired, likert_value, percent
from users.models import User

from . import stats
from .models import Component, Indicator

STAGES = {"initial": "Tajriba boshida", "final": "Tajriba oxirida", "delayed": "Tajribadan keyin"}
STAGE_QUIZZES = {"initial": "initial_quizzes", "final": "final_quizzes", "delayed": "delayed_quizzes"}
LEVELS = {"low": "Past", "medium": "O'rta", "high": "Yuqori"}
# Umumiy daraja (komponentlar o'rtachasi) chegaralari; komponentlarniki admin panelda sozlanadi
OVERALL_MEDIUM_FROM = 40
OVERALL_HIGH_FROM = 70
EXPLANATION_VALUES = {"ok": 1.0, "partial": 0.5, "wrong": 0.0}
# O'zaro baholash ko'rsatkichlari shundan kam baholash (yoki muallif belgilagan izoh) bo'lsa hisoblanmaydi
MIN_PEER_REVIEWS = 2


def level(score, medium_from, high_from):
    if score is None:
        return None
    if score >= high_from:
        return "high"
    return "medium" if score >= medium_from else "low"


def _mean(values):
    return sum(values) / len(values) if values else None


def _round(value):
    return round(value, 1) if value is not None else None


def load_model():
    """Komponentlar ko'rsatkichlari va ularga bog'langan testlar bilan (so'rovlar soni kesimlar sonidan oshmaydi)."""
    indicators = Indicator.objects.prefetch_related(*STAGE_QUIZZES.values()).order_by("order", "id")
    return list(Component.objects.prefetch_related(Prefetch("indicators", queryset=indicators)))


def stage_quizzes(indicator, stage):
    return list(getattr(indicator, STAGE_QUIZZES[stage]).all())


class Data:
    """Bir guruh talabalari uchun kerakli ma'lumotlarni bir marta yuklaydi (har bir talaba uchun alohida so'rov yo'q)."""

    def __init__(self, components, students, stage):
        self.stage = stage
        student_ids = [student.pk for student in students]
        indicators = [indicator for component in components for indicator in component.indicators.all()]
        sources = {indicator.source for indicator in indicators}

        # Testlar va so'rovnomalar
        quiz_ids = {quiz.pk for indicator in indicators for quiz in stage_quizzes(indicator, stage)}
        self.quiz_attempts = {}
        if quiz_ids:
            attempts = QuizAttempt.objects.filter(quiz_id__in=quiz_ids, student_id__in=student_ids).select_related("quiz")
            for attempt in attempts:
                attempt = finalize_if_expired(attempt)
                if attempt.submitted_at:
                    self.quiz_attempts[(attempt.quiz_id, attempt.student_id)] = attempt
        self.likert_questions = defaultdict(list)
        if quiz_ids and Indicator.Source.SURVEY in sources:
            for question in Question.objects.filter(quiz_id__in=quiz_ids, kind=Question.Kind.LIKERT).prefetch_related("choices"):
                self.likert_questions[question.quiz_id].append(question)

        # Laboratoriyalar (faqat tajriba oxirida o'lchanadi)
        self.labs_by_group = defaultdict(list)
        self.attempts_by_student = defaultdict(list)
        if stage == "final" and sources & set(Indicator.TOPIC_SOURCES):
            group_ids = {student.group_id for student in students if student.group_id}
            for lab in mastery.course_order(Lab.objects.filter(groups__in=group_ids).distinct().prefetch_related("groups")):
                for group in lab.groups.all():
                    if group.pk in group_ids:
                        self.labs_by_group[group.pk].append(lab)
            for attempt in LabAttempt.objects.filter(student_id__in=student_ids).only(
                "lab_id", "student_id", "is_correct", "explanation_verdict", "confidence", "created_at"
            ).order_by("id"):
                self.attempts_by_student[attempt.student_id].append(attempt)

        # Buyurtmachi bilan suhbat xabarlari: {(talaba, laboratoriya): [xabarlar]}
        self.interviews = defaultdict(list)
        if stage == "final" and Indicator.Source.INTERVIEW in sources:
            for message in InterviewMessage.objects.filter(student_id__in=student_ids).only("lab_id", "student_id", "revealed"):
                self.interviews[(message.student_id, message.lab_id)].append(message)

        # Talaba yozgan o'zaro baholashlar: {talaba: [baholashlar]}
        self.peer_reviews = defaultdict(list)
        if stage == "final" and sources & set(Indicator.PEER_SOURCES):
            for review in PeerReview.objects.filter(reviewer_id__in=student_ids).select_related("attempt"):
                self.peer_reviews[review.reviewer_id].append(review)

        # O'qituvchi baholari: har bir topshiriq (bosqich) bo'yicha oxirgi baholangan urinish
        self.grades = defaultdict(list)
        if stage == "final" and Indicator.Source.GRADES in sources:
            latest = {}
            for grade in Grade.objects.filter(submission__student_id__in=student_ids).select_related("submission"):
                submission = grade.submission
                key = (submission.student_id, submission.assignment_id, submission.stage_id)
                if key not in latest or submission.attempt_number > latest[key].submission.attempt_number:
                    latest[key] = grade
            for (student_id, _, _), grade in latest.items():
                if grade.max_score:
                    self.grades[student_id].append(100 * grade.score / grade.max_score)

    def labs_for(self, student, indicator):
        labs = self.labs_by_group.get(student.group_id, [])
        return [lab for lab in labs if lab.effective_topic in indicator.topics] if indicator.topics else labs


def common_likert_texts(quizzes, likert_questions):
    """Kesimdagi barcha so'rovnomalarda bor fikrlar: guruhlar o'rtasida faqat bir xil savollar solishtiriladi."""
    texts = None
    for quiz in quizzes:
        quiz_texts = {question.text.strip() for question in likert_questions.get(quiz.pk, [])}
        texts = quiz_texts if texts is None else texts & quiz_texts
    return texts or set()


def indicator_value(indicator, student, data):
    """Talabaning ko'rsatkich qiymati (0-100) yoki None — bu kesimda o'lchanmagan."""
    source = indicator.source
    if source in Indicator.QUIZ_SOURCES:
        quizzes = stage_quizzes(indicator, data.stage)
        attempt = next(
            (data.quiz_attempts[(quiz.pk, student.pk)] for quiz in quizzes if (quiz.pk, student.pk) in data.quiz_attempts),
            None,
        )
        if attempt is None:
            return None
        if source == Indicator.Source.QUIZ:
            return percent(attempt) if attempt.max_score else None
        common = common_likert_texts(quizzes, data.likert_questions)
        values = []
        for question in data.likert_questions.get(attempt.quiz_id, []):
            if question.text.strip() in common:
                value = likert_value(question, attempt.answers.get(str(question.pk), []))
                if value is not None:
                    values.append(value)
        # Likert 1-5 shkalasi 0-100 ga o'tkaziladi: 1 → 0, 3 → 50, 5 → 100
        return 100 * (_mean(values) - 1) / 4 if values else None

    if data.stage != "final":
        return None
    if source == Indicator.Source.GRADES:
        return _mean(data.grades.get(student.pk, []))
    if source in Indicator.AI_SOURCES and not student.ai_allowed:
        return None

    labs = data.labs_for(student, indicator)
    if source == Indicator.Source.INTERVIEW:
        # Talaba suhbatlashgan yoki diagramma yuborgan laboratoriyalar; boshlanmaganlari hisobga olinmaydi
        attempted = {attempt.lab_id for attempt in data.attempts_by_student.get(student.pk, [])}
        values = [
            coverage(lab, data.interviews.get((student.pk, lab.pk), []))
            for lab in labs
            if lab.is_interview and ((student.pk, lab.pk) in data.interviews or lab.pk in attempted)
        ]
        return _mean(values)
    if not labs:
        return None
    lab_ids = {lab.pk for lab in labs}
    attempts = [attempt for attempt in data.attempts_by_student.get(student.pk, []) if attempt.lab_id in lab_ids]
    if source in Indicator.PEER_SOURCES:
        reviews = [review for review in data.peer_reviews.get(student.pk, []) if review.attempt.lab_id in lab_ids]
        if source == Indicator.Source.PEER_ACCURACY:
            return _mean([peer_accuracy(review) for review in reviews]) if len(reviews) >= MIN_PEER_REVIEWS else None
        rated = [review.helpful for review in reviews if review.helpful is not None]
        return 100 * sum(rated) / len(rated) if len(rated) >= MIN_PEER_REVIEWS else None
    if source == Indicator.Source.CALIBRATION:
        result = calibration(attempts)
        return result["score"] if result else None
    solved = {attempt.lab_id for attempt in attempts if attempt.is_correct}
    if source == Indicator.Source.LABS:
        return 100 * len(solved) / len(labs)
    if source == Indicator.Source.MASTERY:
        topics = mastery.student_mastery(labs, attempts)
        return 100 * _mean([state["mastery"] for state in topics.values()])
    # Tushuntirish: yechilgan har bir laboratoriya bo'yicha eng yaxshi baho; tushuntirilmagani — 0
    if not solved:
        return None
    best = defaultdict(float)
    for attempt in attempts:
        if attempt.is_correct and attempt.explanation_verdict:
            best[attempt.lab_id] = max(best[attempt.lab_id], EXPLANATION_VALUES.get(attempt.explanation_verdict, 0.0))
    return 100 * sum(best[lab_id] for lab_id in solved) / len(solved)


def student_profile(components, student, data):
    """{component_id: {"score", "level"}} va umumiy ball/daraja."""
    result = {}
    measured = []
    for component in components:
        total = weights = 0
        for indicator in component.indicators.all():
            value = indicator_value(indicator, student, data)
            if value is not None:
                total += indicator.weight * value
                weights += indicator.weight
        score = total / weights if weights else None
        result[component.pk] = {"score": _round(score), "level": level(score, component.medium_from, component.high_from)}
        if score is not None:
            measured.append(score)
    overall = _mean(measured)
    return result, {"score": _round(overall), "level": level(overall, OVERALL_MEDIUM_FROM, OVERALL_HIGH_FROM)}


def distribution(levels):
    """Darajalar taqsimoti: soni va o'lchanganlar ichidagi ulushi (%)."""
    counts = {key: 0 for key in LEVELS}
    unmeasured = 0
    for value in levels:
        if value is None:
            unmeasured += 1
        else:
            counts[value] += 1
    measured = sum(counts.values())
    return {
        "counts": counts,
        "percents": {key: round(100 * count / measured, 1) if measured else None for key, count in counts.items()},
        "measured": measured,
        "unmeasured": unmeasured,
    }


def summarize(components, profiles):
    """profiles — [(component_scores, overall)]: har bir komponent va umumiy bo'yicha taqsimot va o'rtacha ball."""
    rows = []
    for component in components:
        items = [scores[component.pk] for scores, _ in profiles]
        rows.append(
            {
                "component": component.pk,
                "distribution": distribution([item["level"] for item in items]),
                "mean": _round(_mean([item["score"] for item in items if item["score"] is not None])),
            }
        )
    overall = [item for _, item in profiles]
    return {
        "components": rows,
        "overall": {
            "distribution": distribution([item["level"] for item in overall]),
            "mean": _round(_mean([item["score"] for item in overall if item["score"] is not None])),
        },
    }


def indicator_stages(indicator):
    """Ko'rsatkich qaysi kesimlarda o'lchanadi."""
    if indicator.source in Indicator.QUIZ_SOURCES:
        return [stage for stage in STAGES if stage_quizzes(indicator, stage)]
    return ["final"]


def model_payload(components):
    result = []
    for component in components:
        indicators = [
            {
                "id": indicator.pk,
                "name": indicator.name,
                "source": indicator.source,
                "source_label": indicator.get_source_display(),
                "weight": indicator.weight,
                "topics": indicator.topics,
                "ai_only": indicator.source in Indicator.AI_SOURCES,
                "stages": indicator_stages(indicator),
            }
            for indicator in component.indicators.all()
        ]
        result.append(
            {
                "id": component.pk,
                "name": component.name,
                "description": component.description,
                "medium_from": component.medium_from,
                "high_from": component.high_from,
                # Komponent shu kesimlarda o'lchanadi; kesimlar to'plami har xil bo'lsa, umumiy ball taqqoslanmaydi
                "stages": [stage for stage in STAGES if any(stage in item["stages"] for item in indicators)],
                "indicators": indicators,
            }
        )
    return result


def group_students(group):
    return list(User.objects.filter(role=User.Role.STUDENT, is_active=True, group=group).select_related("group").order_by("last_name", "first_name", "username"))


def group_report(components, group, stage):
    """O'qituvchi uchun: guruh talabalarining komponentlar bo'yicha ballari, darajalari va guruh taqsimoti."""
    students = group_students(group)
    data = Data(components, students, stage)
    profiles = [student_profile(components, student, data) for student in students]
    return {
        "group": {"id": group.pk, "name": group.name, "ai_enabled": group.ai_enabled},
        "stage": stage,
        "students": [
            {
                "id": student.pk,
                "name": student.get_full_name() or student.username,
                "components": {str(key): value for key, value in scores.items()},
                "overall": overall,
            }
            for student, (scores, overall) in zip(students, profiles)
        ],
        "summary": summarize(components, profiles),
    }


COHORTS = ("experimental", "control")


def collect_profiles(components, groups):
    """Har bir guruh va kesim uchun talabalar profillari: [(guruh, talabalar, {kesim: [(ballar, umumiy)]})]."""
    result = []
    for group in groups:
        students = group_students(group)
        by_stage = {}
        for stage in STAGES:
            data = Data(components, students, stage)
            by_stage[stage] = [student_profile(components, student, data) for student in students]
        result.append((group, students, by_stage))
    return result


def cohort_of(group):
    return "experimental" if group.ai_enabled else "control"


def comparison(components, groups, collected=None):
    """Tajriba (AI yoqilgan) va nazorat guruhlari: ikkala kesimdagi darajalar taqsimoti.

    Har bir guruh alohida va guruhlar birlashtirilgan holda (tajriba / nazorat) qaytariladi.
    """
    collected = collect_profiles(components, groups) if collected is None else collected
    by_cohort = {stage: {cohort: [] for cohort in COHORTS} for stage in STAGES}
    group_rows = []
    for group, students, by_stage in collected:
        row = {"id": group.pk, "name": group.name, "ai_enabled": group.ai_enabled, "students": len(students), "stages": {}}
        for stage in STAGES:
            row["stages"][stage] = summarize(components, by_stage[stage])
            by_cohort[stage][cohort_of(group)].extend(by_stage[stage])
        group_rows.append(row)
    cohorts = {
        cohort: {
            "groups": sum(1 for row in group_rows if row["ai_enabled"] == (cohort == "experimental")),
            "students": len(by_cohort["final"][cohort]),
            "stages": {stage: summarize(components, by_cohort[stage][cohort]) for stage in STAGES},
        }
        for cohort in COHORTS
    }
    return {"groups": group_rows, "cohorts": cohorts}


def _r(value, digits=2):
    return round(value, digits) if isinstance(value, (int, float)) and math.isfinite(value) else None


def _rounded(result):
    """Statistik natijani JSON uchun yaxlitlaydi: p-qiymatlar 4 xona, qolganlari 2 xona."""
    if result is None:
        return None
    return {key: (_r(value, 4 if key == "p" else 2) if isinstance(value, float) else value) for key, value in result.items()}


def _describe(values):
    info = stats.describe(values)
    return {"n": info["n"], "mean": _r(info["mean"]), "sd": _r(info["sd"])}


def change(measured, key, before_stage, after_stage):
    """Har bir guruh ichida ikki kesim orasidagi o'zgarish (juftlangan t) va guruhlar o'zgarishlari farqi (Uelch t).

    Faqat ikkala kesimda ham o'lchangan talabalar olinadi.
    """
    result, deltas = {}, {}
    for cohort in COHORTS:
        before, after = measured(before_stage, cohort, key), measured(after_stage, cohort, key)
        both = sorted(set(before) & set(after))
        before_scores = [before[sid]["score"] for sid in both]
        after_scores = [after[sid]["score"] for sid in both]
        deltas[cohort] = [y - x for x, y in zip(before_scores, after_scores)]
        result[cohort] = {
            "n": len(both),
            "before_mean": _r(stats.describe(before_scores)["mean"]),
            "after_mean": _r(stats.describe(after_scores)["mean"]),
            "paired": _rounded(stats.paired_t_test(before_scores, after_scores)),
        }
    # Tajriba guruhi nazoratdan ko'proq o'sganmi (yoki kamroq unutganmi)
    result["difference"] = _rounded(stats.welch_t_test(deltas["experimental"], deltas["control"]))
    return result


def efficiency(components, groups):
    """Tajriba samaradorligi: har bir komponent (va umumiy) bo'yicha, har bir kesimda tajriba va nazorat
    guruhlari solishtiriladi (χ², Uelch t, Mann–Uitni); har bir guruh ichida boshidan oxirigacha o'sish va
    oxiridan kechiktirilgan testgacha bilim saqlanishi (juftlangan t), hamda guruhlar o'rtasidagi farqi (Uelch t).

    Faqat shu kesimda o'lchangan talabalar olinadi.
    """
    collected = collect_profiles(components, groups)
    # {kesim: {guruh: {talaba_id: {komponent_kaliti: ScoreDict}}}}
    scores = {stage: {cohort: {} for cohort in COHORTS} for stage in STAGES}
    for group, students, by_stage in collected:
        for stage in STAGES:
            for student, (component_scores, overall) in zip(students, by_stage[stage]):
                scores[stage][cohort_of(group)][student.pk] = {**{str(key): value for key, value in component_scores.items()}, "overall": overall}

    def measured(stage, cohort, key):
        return {sid: item[key] for sid, item in scores[stage][cohort].items() if item[key]["score"] is not None}

    rows = []
    for key, name in [(str(component.pk), component.name) for component in components] + [("overall", "Umumiy")]:
        row = {"key": key, "name": name, "stages": {}}
        for stage in STAGES:
            groups_data = {cohort: measured(stage, cohort, key) for cohort in COHORTS}
            values = {cohort: [item["score"] for item in groups_data[cohort].values()] for cohort in COHORTS}
            counts = {cohort: [sum(1 for item in groups_data[cohort].values() if item["level"] == level) for level in LEVELS] for cohort in COHORTS}
            means = {cohort: stats.describe(values[cohort])["mean"] for cohort in COHORTS}
            ratio = means["experimental"] / means["control"] if means["experimental"] is not None and means["control"] else None
            row["stages"][stage] = {
                "describe": {cohort: _describe(values[cohort]) for cohort in COHORTS},
                "levels": counts,
                "chi_square": _rounded(stats.chi_square([counts["experimental"], counts["control"]])),
                "t_test": _rounded(stats.welch_t_test(values["experimental"], values["control"])),
                "mann_whitney": _rounded(stats.mann_whitney(values["experimental"], values["control"])),
                # Samaradorlik koeffitsienti: tajriba guruhi o'rtachasi / nazorat guruhi o'rtachasi (> 1 — tajriba yaxshiroq)
                "efficiency_ratio": _r(ratio, 3),
            }
        # O'sish (boshi → oxiri) va bilim saqlanishi (oxiri → kechiktirilgan test)
        row["growth"] = change(measured, key, "initial", "final")
        row["retention"] = change(measured, key, "final", "delayed")
        rows.append(row)
    return {
        "alpha": stats.ALPHA,
        "min_expected": stats.MIN_EXPECTED,
        "students": {cohort: sum(len(students) for group, students, _ in collected if cohort_of(group) == cohort) for cohort in COHORTS},
        "rows": rows,
    }
