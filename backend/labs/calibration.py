"""O'z bilimini baholash aniqligi (kalibrlash): talaba tekshirishdan oldin belgilagan ishonch natija bilan solishtiriladi.

Ishonch 1-5 shkaladan ehtimolga o'tkaziladi (1 → 0, 3 → 0.5, 5 → 1). Har bir laboratoriyadan bitta mulohaza
olinadi — ishonch belgilangan birinchi tekshiruv: undan keyingi urinishlarda talaba tekshiruv natijasini allaqachon
ko'rgan bo'ladi, ya'ni bu o'zini baholash emas.

- Brier ko'rsatkichi: (ehtimol − natija)² o'rtachasi, 0 — mukammal; kalibrlash bali = 100 × (1 − Brier);
- og'ish (bias): o'rtacha ishonch − o'rtacha natija (foizda); musbat — o'ziga ortiqcha ishonadi, manfiy — kam.

Bu ko'rsatkich AI ga bog'liq emas: tajriba va nazorat guruhlarida bir xil o'lchanadi.
"""

MIN_LABS = 3  # bundan kam laboratoriya bo'lsa, ko'rsatkich hisoblanmaydi (tasodif ta'siri katta)


def probability(confidence):
    return (confidence - 1) / 4


def judgments(attempts):
    """attempts — eskisidan yangisiga. Har bir laboratoriya uchun (ehtimol, natija): ishonch belgilangan birinchi urinish."""
    seen = set()
    result = []
    for attempt in attempts:
        if attempt.confidence is None or attempt.lab_id in seen:
            continue
        seen.add(attempt.lab_id)
        result.append((probability(attempt.confidence), 1.0 if attempt.is_correct else 0.0))
    return result


def calibration(attempts):
    """Qaytaradi: {"n", "score", "brier", "bias"} yoki None (laboratoriyalar MIN_LABS dan kam)."""
    items = judgments(attempts)
    if len(items) < MIN_LABS:
        return None
    brier = sum((p - o) ** 2 for p, o in items) / len(items)
    bias = sum(p - o for p, o in items) / len(items)
    return {"n": len(items), "score": 100 * (1 - brier), "brier": brier, "bias": 100 * bias}
