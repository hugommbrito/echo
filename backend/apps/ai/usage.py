"""Per-user AI spend, from `AIRequestLog` (estimates, see `apps.ai.pricing`)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db.models import Count, Sum

from apps.ai.models import AIRequestLog, KeySource


def _usd(value) -> float:
    return float(Decimal(str(value or 0)).quantize(Decimal("0.000001")))


def _summary(qs) -> dict:
    by_provider = {
        row["provider"]: row["total"] or 0
        for row in qs.values("provider").annotate(total=Sum("estimated_cost_usd"))
    }
    totals = qs.aggregate(total=Sum("estimated_cost_usd"), requests=Count("id"))
    return {
        "anthropic_usd": _usd(by_provider.get("anthropic")),
        "openai_usd": _usd(by_provider.get("openai")),
        "total_usd": _usd(totals["total"]),
        "requests": totals["requests"] or 0,
    }


def ai_usage(user) -> dict:
    """Runs inside the request's owner context (`AIRequestLog.objects` is scoped)."""
    today = user.local_today()
    month_start = today.replace(day=1)
    month_start_dt = dt.datetime.combine(month_start, dt.time.min, tzinfo=user.tzinfo)
    qs = AIRequestLog.objects.all()
    by_source = {
        row["key_source"]: row["total"] or 0
        for row in qs.values("key_source").annotate(total=Sum("estimated_cost_usd"))
    }
    return {
        "month": {
            "starts_on": month_start,
            **_summary(qs.filter(created_at__gte=month_start_dt)),
        },
        "all_time": _summary(qs),
        "by_key_source": {
            "user_usd": _usd(by_source.get(KeySource.USER)),
            "global_usd": _usd(by_source.get(KeySource.GLOBAL)),
        },
    }
