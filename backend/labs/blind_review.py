"""Ko'r baholash: navbat va AI–o'qituvchi baholari mosligi.

Navbatga har bir talabaning har bir laboratoriya bo'yicha baholangan (eng yuqori) ishi kiradi.
O'qituvchiga ish talaba ismisiz, AI bahosi va izohisiz, har bir baholovchi uchun o'z tasodifiy
tartibida beriladi (ketma-ket bir talabaning ishlari chiqib, bir-biriga ta'sir qilmasligi uchun).

Moslik ko'rsatkichlari:
- Pirson korrelyatsiyasi (r) — ballar birga o'zgaradimi;
- o'rtacha mutlaq farq va o'rtacha farq (tizim − o'qituvchi): tizim qattiqroq yoki yumshoqroqmi;
- Bland–Altman chegaralari: farqlarning 95% shu oraliqda;
- 5 balli shkaladagi baho (2/3/4/5) bo'yicha to'liq moslik ulushi va kvadratik vaznli Kohen kappasi.
"""
import hashlib
import hmac
import math

from django.conf import settings

from .models import BlindReview, LabGrade

# 100 ballik bahodan 5 ballik bahoga (oliy ta'limda keng qo'llanadigan chegaralar)
GRADE_BANDS = [(86, 5), (71, 4), (55, 3), (0, 2)]
BAND_VALUES = [2, 3, 4, 5]


def band(score):
    return next(mark for threshold, mark in GRADE_BANDS if score >= threshold)


def _order_key(reviewer_id, attempt_id):
    digest = hmac.new(settings.SECRET_KEY.encode(), f"blind:{reviewer_id}:{attempt_id}".encode(), hashlib.sha256)
    return digest.hexdigest()


def queue(labs, reviewer):
    """Baholovchi hali baholamagan ishlar (LabGrade), uning tasodifiy tartibida."""
    grades = (
        LabGrade.objects.filter(lab__in=labs)
        .exclude(attempt__blind_reviews__reviewer=reviewer)
        .select_related("lab", "attempt")
    )
    return sorted(grades, key=lambda grade: _order_key(reviewer.pk, grade.attempt_id))


def item_payload(grade):
    """Baholovchiga ko'rsatiladigan ish: talaba, AI bahosi, izohi va tuzatilgan diagrammasiz."""
    lab, attempt = grade.lab, grade.attempt
    feedback = attempt.feedback or {}
    return {
        "attempt_id": attempt.pk,
        "lab": {
            "id": lab.pk,
            "title": lab.title,
            "kind": lab.kind,
            "description": lab.description,
            "setup_sql": lab.setup_sql,
            "solution_sql": lab.solution_sql,
            "reference_diagram": lab.reference_diagram,
        },
        "code": attempt.sql_code,
        "diagram": attempt.diagram,
        "is_correct": attempt.is_correct,
        "check": {"error": feedback.get("error"), "differences": feedback.get("differences") or []},
    }


def _mean(values):
    return sum(values) / len(values)


def pearson(xs, ys):
    if len(xs) < 2:
        return None
    mx, my = _mean(xs), _mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if not sxx or not syy:
        return None
    return sxy / math.sqrt(sxx * syy)


def weighted_kappa(a, b, categories=BAND_VALUES):
    """Kvadratik vaznli Kohen kappasi (1 — to'liq moslik, 0 — tasodifiy darajada)."""
    n = len(a)
    if n < 2:
        return None
    k = len(categories)
    index = {value: position for position, value in enumerate(categories)}
    observed = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        observed[index[x]][index[y]] += 1
    rows = [sum(row) for row in observed]
    cols = [sum(observed[i][j] for i in range(k)) for j in range(k)]
    weight = lambda i, j: (i - j) ** 2 / (k - 1) ** 2  # noqa: E731
    disagreement = sum(weight(i, j) * observed[i][j] for i in range(k) for j in range(k)) / n
    expected = sum(weight(i, j) * rows[i] * cols[j] for i in range(k) for j in range(k)) / (n * n)
    if not expected:
        return None
    return 1 - disagreement / expected


def _round(value, digits=3):
    return None if value is None else round(value, digits)


def agreement_stats(reviews):
    """reviews: BlindReview ro'yxati. Tizim (ai_score) va o'qituvchi (score) baholari mosligi."""
    n = len(reviews)
    stats = {"count": n}
    if not n:
        return stats
    system = [review.ai_score for review in reviews]
    teacher = [review.score for review in reviews]
    diffs = [s - t for s, t in zip(system, teacher)]
    mean_diff = _mean(diffs)
    sd = math.sqrt(sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)) if n > 1 else None
    system_bands = [band(score) for score in system]
    teacher_bands = [band(score) for score in teacher]
    stats.update(
        pearson_r=_round(pearson(system, teacher)),
        mean_abs_diff=_round(_mean([abs(d) for d in diffs]), 1),
        mean_diff=_round(mean_diff, 1),
        limits_of_agreement=[_round(mean_diff - 1.96 * sd, 1), _round(mean_diff + 1.96 * sd, 1)] if sd is not None else None,
        within_10=_round(sum(1 for d in diffs if abs(d) <= 10) / n),
        band_agreement=_round(sum(1 for s, t in zip(system_bands, teacher_bands) if s == t) / n),
        weighted_kappa=_round(weighted_kappa(system_bands, teacher_bands)),
        system_mean=_round(_mean(system), 1),
        teacher_mean=_round(_mean(teacher), 1),
    )
    return stats


def agreement(labs, reviewer=None):
    """Umumiy, manba bo'yicha (AI / avtomatik) moslik va diagramma uchun juftliklar.

    reviewer berilsa — faqat uning baholari (o'qituvchi faqat o'zi baholagan ishlarning AI bahosini ko'radi)."""
    reviews = BlindReview.objects.filter(attempt__lab__in=labs).select_related("attempt__lab")
    if reviewer is not None:
        reviews = reviews.filter(reviewer=reviewer)
    reviews = list(reviews)
    return {
        "overall": agreement_stats(reviews),
        "by_source": {
            source: agreement_stats([review for review in reviews if review.ai_source == source])
            for source in LabGrade.Source.values
        },
        "pairs": [
            {
                "lab_id": review.attempt.lab_id,
                "lab_kind": review.attempt.lab.kind,
                "system": review.ai_score,
                "teacher": review.score,
                "source": review.ai_source,
            }
            for review in reviews
        ],
        "bands": [{"min": threshold, "mark": mark} for threshold, mark in GRADE_BANDS],
    }
