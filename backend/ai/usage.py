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
    "input_tokens": Sum("input_tokens"),
    "output_tokens": Sum("output_tokens"),
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
        "input_tokens": values["input_tokens"] or 0,
        "output_tokens": values["output_tokens"] or 0,
    }
    row["cost"] = cost(row["input_tokens"], row["output_tokens"])
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
