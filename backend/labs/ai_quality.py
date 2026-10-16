"""AI sifatini nazorat qilish: o'qituvchi AI yozgan matnlarni baholaydi, natijasi — AI ishonchliligi ko'rsatkichlari.

Baholanadigan matnlar: urinishlardagi AI maslahatlari (har bir daraja alohida) va yechimni tushuntirish bo'yicha
AI izohlari. Murabbiy va buyurtmachi suhbatlari kirmaydi: ular talabaga shaxsiy deb va'da qilingan.
O'qituvchiga talaba ismi ko'rsatilmaydi; matnlar uning o'z tasodifiy tartibida beriladi.

Xulosada har bir baho ulushi va 95% ishonch oralig'i (Wilson) beriladi — dissertatsiyada "AI qanchalik
ishonchli" degan savolga raqam bilan javob berish uchun.
"""
import hashlib
import hmac
import math

from django.conf import settings

from .er import diagram_to_text
from .models import AIOutputReview, LabAttempt

Z95 = 1.959964


def wilson(successes, total):
    """Ulush uchun 95% Wilson ishonch oralig'i (foizda) yoki None."""
    if not total:
        return None
    p = successes / total
    denominator = 1 + Z95**2 / total
    centre = (p + Z95**2 / (2 * total)) / denominator
    margin = Z95 * math.sqrt(p * (1 - p) / total + Z95**2 / (4 * total**2)) / denominator
    return [round(100 * max(0.0, centre - margin), 1), round(100 * min(1.0, centre + margin), 1)]


def outputs(attempts):
    """Urinishlardagi baholanadigan AI matnlari: (urinish, tur, daraja, matn)."""
    for attempt in attempts:
        hints = list(attempt.ai_hints) or ([attempt.ai_advice] if attempt.ai_advice else [])
        for index, text in enumerate(hints, start=1):
            if isinstance(text, str) and text.strip():
                yield attempt, AIOutputReview.Kind.HINT, index, text
        if attempt.explanation_feedback.strip():
            yield attempt, AIOutputReview.Kind.EXPLANATION, 0, attempt.explanation_feedback


def _order_key(reviewer_id, attempt_id, kind, level):
    digest = hmac.new(settings.SECRET_KEY.encode(), f"aiq:{reviewer_id}:{attempt_id}:{kind}:{level}".encode(), hashlib.sha256)
    return digest.hexdigest()


def scope(groups):
    return LabAttempt.objects.filter(student__group__in=groups).select_related("lab")


def next_item(groups, reviewer):
    """Baholovchi hali baholamagan navbatdagi AI matni (talaba ismisiz) yoki None."""
    done = set(AIOutputReview.objects.filter(reviewer=reviewer).values_list("attempt_id", "kind", "level"))
    candidates = [
        item
        for item in outputs(scope(groups).exclude(ai_hints=[], ai_advice="", explanation_feedback=""))
        if (item[0].pk, item[1], item[2]) not in done
    ]
    if not candidates:
        return None
    attempt, kind, level, text = min(candidates, key=lambda item: _order_key(reviewer.pk, item[0].pk, item[1], item[2]))
    lab = attempt.lab
    work = diagram_to_text(attempt.diagram) if attempt.diagram else attempt.sql_code
    return {
        "attempt": attempt.pk,
        "kind": kind,
        "kind_label": AIOutputReview.Kind(kind).label,
        "level": level,
        "lab": {"title": lab.title, "description": lab.description},
        "work": work,
        "is_correct": attempt.is_correct,
        "differences": (attempt.feedback or {}).get("differences") or [],
        "explanation": attempt.self_explanation if kind == AIOutputReview.Kind.EXPLANATION else "",
        "verdict": attempt.get_explanation_verdict_display() if kind == AIOutputReview.Kind.EXPLANATION else "",
        "text": text,
    }


def summary(groups):
    """Har bir tur va baho bo'yicha soni, ulushi va 95% ishonch oralig'i."""
    reviews = list(AIOutputReview.objects.filter(attempt__in=scope(groups)).values_list("kind", "rating"))
    result = []
    for kind, kind_label in AIOutputReview.Kind.choices:
        ratings = [rating for item_kind, rating in reviews if item_kind == kind]
        total = len(ratings)
        result.append(
            {
                "kind": kind,
                "label": kind_label,
                "total": total,
                "ratings": [
                    {
                        "rating": rating,
                        "label": label,
                        "count": ratings.count(rating),
                        "percent": round(100 * ratings.count(rating) / total, 1) if total else None,
                        "ci95": wilson(ratings.count(rating), total),
                    }
                    for rating, label in AIOutputReview.Rating.choices
                ],
            }
        )
    return result
