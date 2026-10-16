"""AI xarajati hisoboti: so'rovlar, tokenlar va taxminiy narx (AIUsage yozuvlaridan)."""
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import AIUsage

TOTALS = {
    "requests": Count("id"),
    "failed": Count("id", filter=Q(ok=False)),
    # Nomlar maydon nomlaridan farq qiladi: annotate'da bir xil nom keyingi Sum'larni buzadi
    "sum_input": Sum("input_tokens"),
    "sum_output": Sum("output_tokens"),
    "sum_cache_read": Sum("cache_read_tokens"),
    # Narxi saqlangan yozuvlar xarajati va narxi saqlanmagan (eski) yozuvlar tokenlari
    "stored_cost": Sum("cost"),
    "unpriced_input": Sum("input_tokens", filter=Q(cost__isnull=True)),
    "unpriced_output": Sum("output_tokens", filter=Q(cost__isnull=True)),
}


def cost(input_tokens, output_tokens):
    total = (
        input_tokens * settings.AI_PRICE_INPUT_PER_MTOK + output_tokens * settings.AI_PRICE_OUTPUT_PER_MTOK
    ) / 1_000_000
    return round(total, 4)


def _row(values):
    row = {
        "requests": values["requests"] or 0,
        "failed": values["failed"] or 0,
        "input_tokens": values["sum_input"] or 0,
        "output_tokens": values["sum_output"] or 0,
        "cache_read_tokens": values["sum_cache_read"] or 0,
    }
    row["cost"] = round(
        (values["stored_cost"] or 0) + cost(values["unpriced_input"] or 0, values["unpriced_output"] or 0), 4
    )
    return row


def _start_of(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def usage_report(days=30):
    today = timezone.localdate()
    period_start = today - timedelta(days=days - 1)
    month_start = today.replace(day=1)
    previous_month_start = (month_start - timedelta(days=1)).replace(day=1)
    usage = AIUsage.objects.all()
    period = usage.filter(created_at__gte=_start_of(period_start))

    daily = {
        item["day"]: _row(item)
        for item in period.annotate(day=TruncDate("created_at")).values("day").annotate(**TOTALS)
    }
    labels = dict(AIUsage.Purpose.choices)
    return {
        "days": days,
        "price": {
            "input_per_mtok": settings.AI_PRICE_INPUT_PER_MTOK,
            "output_per_mtok": settings.AI_PRICE_OUTPUT_PER_MTOK,
            "fast_input_per_mtok": settings.AI_FAST_PRICE_INPUT_PER_MTOK,
            "fast_output_per_mtok": settings.AI_FAST_PRICE_OUTPUT_PER_MTOK,
            "configured": bool(settings.AI_PRICE_INPUT_PER_MTOK or settings.AI_PRICE_OUTPUT_PER_MTOK),
        },
        "today": _row(usage.filter(created_at__gte=_start_of(today)).aggregate(**TOTALS)),
        "month": _row(usage.filter(created_at__gte=_start_of(month_start)).aggregate(**TOTALS)),
        "previous_month": _row(
            usage.filter(
                created_at__gte=_start_of(previous_month_start), created_at__lt=_start_of(month_start)
            ).aggregate(**TOTALS)
        ),
        "period": _row(period.aggregate(**TOTALS)),
        # Bo'sh kunlar ham beriladi: grafikda uzilish bo'lmasin
        "daily": [
            {"date": day.isoformat(), **daily.get(day, _row({key: 0 for key in TOTALS}))}
            for day in (period_start + timedelta(days=offset) for offset in range(days))
        ],
        "by_purpose": sorted(
            (
                {"purpose": item["purpose"], "label": labels.get(item["purpose"], item["purpose"]), **_row(item)}
                for item in period.values("purpose").annotate(**TOTALS)
            ),
            key=lambda row: row["input_tokens"] + row["output_tokens"],
            reverse=True,
        ),
        "by_model": sorted(
            ({"model": item["model_name"] or "—", **_row(item)} for item in period.values("model_name").annotate(**TOTALS)),
            key=lambda row: row["requests"],
            reverse=True,
        ),
    }
