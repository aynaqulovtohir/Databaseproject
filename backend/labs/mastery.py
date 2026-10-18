"""Moslashuvchan o'quv yo'li: mavzular bo'yicha o'zlashtirish (Bayesian Knowledge Tracing) va keyingi tavsiya.

BKT — har bir mavzu uchun "talaba ko'nikmani egallagan" ehtimoli. Har bir kuzatuvdan (urinish to'g'ri/xato)
keyin Bayes qoidasi bilan yangilanadi, so'ng o'rganish ehtimoli qo'shiladi. Parametrlar adabiyotdagi odatiy
boshlang'ich qiymatlar (Corbett & Anderson, 1995); ular sozlanmagan, shuning uchun natija — yo'nalish, baho emas.

Kuzatuvlar: har bir laboratoriyada birinchi to'g'ri javobgacha bo'lgan dastlabki MAX_OBSERVATIONS urinish.
Shunda bitta laboratoriyada ko'p marta "sinab ko'rish" bir mavzuni haddan tashqari tushirib yubormaydi.
LLM ishlatilmaydi: hisob tez, arzon va tushuntirib berish mumkin.
"""
from collections import defaultdict

from .models import Lab, LabAttempt
from .sequence import chain, lock_map

P_INIT = 0.2  # boshlanishda bilish ehtimoli
P_LEARN = 0.15  # har bir imkoniyatda o'rganish
P_SLIP = 0.1  # bilsa ham xato qilish
P_GUESS = 0.2  # bilmasa ham to'g'ri topish
MASTERED = 0.95
MAX_OBSERVATIONS = 3
TOPIC_ORDER = [choice for choice, _ in Lab.Topic.choices]
TOPIC_LABELS = dict(Lab.Topic.choices)


def update(p_known, correct):
    if correct:
        evidence = p_known * (1 - P_SLIP)
        posterior = evidence / (evidence + (1 - p_known) * P_GUESS)
    else:
        evidence = p_known * P_SLIP
        posterior = evidence / (evidence + (1 - p_known) * (1 - P_GUESS))
    return posterior + (1 - posterior) * P_LEARN


def observations(attempts):
    """attempts — bitta laboratoriyadagi urinishlar (eskisidan yangisiga). Birinchi to'g'risigacha, ko'pi bilan 3 ta."""
    result = []
    for attempt in attempts:
        result.append(attempt.is_correct)
        if attempt.is_correct or len(result) >= MAX_OBSERVATIONS:
            break
    return result


def student_mastery(labs, attempts):
    """labs — talabaga ko'rinadigan laboratoriyalar, attempts — uning urinishlari (eskisidan yangisiga).

    Qaytaradi: {mavzu: {"mastery", "labs", "solved", "observations"}} — faqat laboratoriyasi bor mavzular.
    """
    by_lab = defaultdict(list)
    for attempt in attempts:
        by_lab[attempt.lab_id].append(attempt)
    topics = {}
    # Laboratoriyalar o'z mavzusida birinchi urinish vaqti tartibida "o'tiladi"
    # (urinishsiz laboratoriyalar kuzatuv bermaydi, ular faqat sanaladi)
    attempted = sorted((lab for lab in labs if by_lab.get(lab.pk)), key=lambda lab: by_lab[lab.pk][0].created_at)
    for lab in attempted + [lab for lab in labs if not by_lab.get(lab.pk)]:
        topic = topics.setdefault(lab.effective_topic, {"mastery": P_INIT, "labs": 0, "solved": 0, "observations": 0})
        topic["labs"] += 1
        lab_attempts = by_lab.get(lab.pk, [])
        if any(attempt.is_correct for attempt in lab_attempts):
            topic["solved"] += 1
        for correct in observations(lab_attempts):
            topic["mastery"] = update(topic["mastery"], correct)
            topic["observations"] += 1
    return topics


def recommend(labs, topics, solved_ids):
    """Kurs tartibida birinchi o'zlashtirilmagan mavzudagi birinchi yechilmagan laboratoriya."""
    unsolved = [lab for lab in labs if lab.pk not in solved_ids]
    for topic in TOPIC_ORDER:
        state = topics.get(topic)
        if state is None or state["mastery"] >= MASTERED:
            continue
        candidates = [lab for lab in unsolved if lab.effective_topic == topic]
        if candidates:
            started = state["observations"] > 0
            reason = (
                f"«{TOPIC_LABELS[topic]}» mavzusi hali to'liq o'zlashtirilmagan ({round(100 * state['mastery'])}%): "
                "keyingi mavzularga o'tishdan oldin uni mustahkamlang."
                if started
                else f"Kurs tartibida navbatdagi mavzu: «{TOPIC_LABELS[topic]}»."
            )
            return candidates[0], reason
    if unsolved:
        return unsolved[0], "Barcha mavzular yaxshi o'zlashtirilgan: qolgan laboratoriyalarni ham yeching."
    return None, ""


def topics_payload(topics):
    return [
        {
            "topic": topic,
            "label": TOPIC_LABELS[topic],
            "mastery": round(100 * topics[topic]["mastery"]),
            "mastered": topics[topic]["mastery"] >= MASTERED,
            "labs": topics[topic]["labs"],
            "solved": topics[topic]["solved"],
        }
        for topic in TOPIC_ORDER
        if topic in topics
    ]


def course_order(labs):
    """Talabaga ko'rsatiladigan tartib (yangisi yuqorida — tayyor laboratoriyalar shu tartibda qo'shilgan)."""
    return sorted(labs, key=lambda lab: (-lab.created_at.timestamp(), -lab.pk))


def student_report(student, labs):
    labs = course_order(labs)
    attempts = list(
        LabAttempt.objects.filter(student=student, lab__in=labs).only("lab_id", "is_correct", "created_at").order_by("id")
    )
    topics = student_mastery(labs, attempts)
    solved_ids = {attempt.lab_id for attempt in attempts if attempt.is_correct}
    # Modullar zanjiri: navbatdagi (birinchi yechilmagan) laboratoriya o'qituvchi belgilagan tartibda
    chained = [item for item in chain(labs) if item.pk not in solved_ids]
    if chained:
        lab = chained[0]
        reason = f"«{lab.module.title}» modulida navbatdagi laboratoriya: keyingilari shu yechilgandan keyin ochiladi."
    else:
        locks = lock_map(student, labs)
        lab, reason = recommend([item for item in labs if locks[item.pk] is None], topics, solved_ids)
    return {
        "topics": topics_payload(topics),
        "next": {"id": lab.pk, "title": lab.title, "topic": lab.effective_topic, "reason": reason} if lab else None,
    }


def group_report(students, labs):
    """O'qituvchi uchun: har bir talabaning mavzular bo'yicha o'zlashtirishi (foizda)."""
    labs = course_order(labs)
    by_student = defaultdict(list)
    for attempt in LabAttempt.objects.filter(student__in=students, lab__in=labs).only(
        "student_id", "lab_id", "is_correct", "created_at"
    ).order_by("id"):
        by_student[attempt.student_id].append(attempt)
    present = {lab.effective_topic for lab in labs}
    topics = [{"topic": topic, "label": TOPIC_LABELS[topic]} for topic in TOPIC_ORDER if topic in present]
    rows = []
    for student in students:
        mastery = student_mastery(labs, by_student.get(student.pk, []))
        rows.append(
            {
                "id": student.pk,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "group": student.group.name if student.group else "",
                "mastery": {topic: round(100 * state["mastery"]) for topic, state in mastery.items()},
            }
        )
    return {"topics": topics, "students": rows}
