"""O'zaro baholash: talabalar guruhdoshlarining ER-diagrammalarini rubrika bo'yicha anonim baholaydi.

Kim baholaydi: laboratoriyani o'zi to'g'ri yechgan talaba — shunda boshqaning ishini ko'rib ko'chirib olmaydi
va solishtirish uchun o'z tayanchi bo'ladi. Har bir laboratoriyada ko'pi bilan REVIEWS_PER_LAB ta ish, har bir
guruhdoshning faqat bitta ishi (oxirgi topshirgani). Navbatda avval kam baholangan ishlar turadi, bir xil
bo'lsa — baholovchining o'z tasodifiy tartibida.

O'lchanadigan ko'rsatkichlar (kompetentlik modeli):
- baholash aniqligi: baholovchining tuzilma mezonlari (obyektlar, atributlar, bog'lanishlar) bo'yicha bali
  tizim bahosiga (namunaga moslik, er.compare) qanchalik yaqin — 100 − |farq|;
- izohlar foydaliligi: muallif "foydali" deb belgilagan izohlar ulushi.

Ikkalasi ham AI ga bog'liq emas: tajriba va nazorat guruhlarida bir xil ishlaydi.
"""
import hashlib
import hmac

from django.conf import settings

from .er import compare
from .models import Lab, LabAttempt, PeerReview

REVIEWS_PER_LAB = 3
MIN_COMMENT_LENGTH = 20
MAX_COMMENT_LENGTH = 2000
SCALE = (1, 2, 3, 4)
CRITERIA = [
    {"key": "entities", "name": "Obyektlar", "hint": "Kerakli obyektlar bor, ortiqchasi yo'q"},
    {"key": "attributes", "name": "Atributlar va kalitlar", "hint": "Kerakli atributlar va har bir obyektda asosiy kalit"},
    {"key": "relationships", "name": "Bog'lanishlar va kardinallik", "hint": "Bog'lanishlar to'g'ri, kardinallik (1 yoki N) mos"},
    {"key": "clarity", "name": "Nomlash va tushunarlilik", "hint": "Nomlar aniq, diagrammani o'qish oson"},
]
# Tizim bahosi bilan solishtiriladigan mezonlar (nomlash va tushunarlilikni tizim o'lchamaydi)
STRUCTURAL = ("entities", "attributes", "relationships")
SCALE_LABELS = {1: "Ko'p xato", 2: "Sezilarli kamchilik", 3: "Kichik kamchilik", 4: "To'liq to'g'ri"}


class ReviewError(ValueError):
    pass


def validate(scores, comment):
    if not isinstance(scores, dict) or set(scores) != {item["key"] for item in CRITERIA}:
        raise ReviewError("Har bir mezonga ball qo'ying.")
    if any(isinstance(value, bool) or value not in SCALE for value in scores.values()):
        raise ReviewError("Ball 1 dan 4 gacha bo'lishi kerak.")
    if not isinstance(comment, str) or len(comment.strip()) < MIN_COMMENT_LENGTH:
        raise ReviewError(f"Izoh kamida {MIN_COMMENT_LENGTH} belgi bo'lsin: nima yaxshi va nimani yaxshilash mumkinligini yozing.")
    if len(comment) > MAX_COMMENT_LENGTH:
        raise ReviewError(f"Izoh {MAX_COMMENT_LENGTH} belgidan oshmasin.")
    return {key: int(value) for key, value in scores.items()}, comment.strip()


def structural_score(scores):
    """Baholovchining tuzilma mezonlari bo'yicha bali, 0-100 (1 → 0, 4 → 100)."""
    return 100 * (sum(scores[key] for key in STRUCTURAL) / len(STRUCTURAL) - 1) / 3


def accuracy(review):
    """Baholash aniqligi, 0-100: baholovchi bali tizim bahosiga qanchalik yaqin."""
    return 100 - abs(structural_score(review.scores) - 100 * review.reference_ratio)


def eligible(lab, student):
    """(baholay oladimi, sabab)."""
    if lab.kind != Lab.Kind.ER:
        return False, "O'zaro baholash faqat ER-diagramma laboratoriyalarida."
    if not LabAttempt.objects.filter(lab=lab, student=student, is_correct=True).exists():
        return False, "Guruhdoshlaringiz ishini baholash uchun avval laboratoriyani o'zingiz to'g'ri yeching."
    return True, ""


def _order_key(reviewer_id, attempt_id):
    digest = hmac.new(settings.SECRET_KEY.encode(), f"peer:{reviewer_id}:{attempt_id}".encode(), hashlib.sha256)
    return digest.hexdigest()


def next_attempt(lab, reviewer):
    """Baholovchiga navbatdagi ish yoki None. Faqat o'z guruhidagi, o'zi baholamagan guruhdoshlarning oxirgi topshirgan ishi."""
    if reviewer.group_id is None:
        return None
    reviewed_students = set(
        PeerReview.objects.filter(reviewer=reviewer, attempt__lab=lab).values_list("attempt__student_id", flat=True)
    )
    latest = {}
    for attempt in LabAttempt.objects.filter(
        lab=lab, is_submission=True, student__group_id=reviewer.group_id, student__is_active=True
    ).exclude(student=reviewer).order_by("id"):
        latest[attempt.student_id] = attempt
    candidates = [attempt for student_id, attempt in latest.items() if student_id not in reviewed_students]
    if not candidates:
        return None
    counts = {}
    for attempt_id in PeerReview.objects.filter(attempt__in=candidates).values_list("attempt_id", flat=True):
        counts[attempt_id] = counts.get(attempt_id, 0) + 1
    return min(candidates, key=lambda attempt: (counts.get(attempt.pk, 0), _order_key(reviewer.pk, attempt.pk)))


def create(lab, reviewer, attempt_id, scores, comment):
    """Baholashni saqlaydi. Ish baholovchiga hozir navbatda berilgan ish bo'lishi shart (o'zi tanlay olmaydi)."""
    ok, reason = eligible(lab, reviewer)
    if not ok:
        raise ReviewError(reason)
    if PeerReview.objects.filter(reviewer=reviewer, attempt__lab=lab).count() >= REVIEWS_PER_LAB:
        raise ReviewError("Bu laboratoriyada baholash uchun ishlar tugadi. Rahmat!")
    expected = next_attempt(lab, reviewer)
    if expected is None or expected.pk != attempt_id:
        raise ReviewError("Bu ish sizga baholash uchun berilmagan. Sahifani yangilang.")
    scores, comment = validate(scores, comment)
    return PeerReview.objects.create(
        attempt=expected,
        reviewer=reviewer,
        scores=scores,
        comment=comment,
        reference_ratio=compare(expected.diagram or {"entities": [], "relationships": []}, lab.reference_diagram)["ratio"],
    )


def state(lab, student):
    """Talaba uchun: baholanadigan navbatdagi ish (ismsiz) va o'z ishlariga berilgan baholar (baholovchi ismisiz)."""
    ok, reason = eligible(lab, student)
    written = PeerReview.objects.filter(reviewer=student, attempt__lab=lab).count()
    current = None
    if ok and written < REVIEWS_PER_LAB:
        attempt = next_attempt(lab, student)
        if attempt is not None:
            current = {"attempt_id": attempt.pk, "diagram": attempt.diagram}
        else:
            reason = "Hozircha baholash uchun guruhdoshlaringizning topshirilgan ishlari yo'q."
    elif ok:
        reason = "Bu laboratoriyada barcha baholashlarni bajardingiz. Rahmat!"
    received = PeerReview.objects.filter(attempt__lab=lab, attempt__student=student).order_by("-id")
    return {
        "criteria": CRITERIA,
        "scale": [{"value": value, "label": label} for value, label in SCALE_LABELS.items()],
        "per_lab": REVIEWS_PER_LAB,
        "written": written,
        "current": current,
        "reason": "" if current else reason,
        "received": [
            {"id": review.pk, "scores": review.scores, "comment": review.comment, "helpful": review.helpful, "created_at": review.created_at}
            for review in received
        ],
    }
