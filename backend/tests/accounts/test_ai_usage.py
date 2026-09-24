"""`GET /me/ai-usage/`: the learner's own estimated spend, by month, provider and key origin."""

import datetime as dt
from decimal import Decimal

import pytest
import time_machine

from apps.ai.models import AIRequestLog
from apps.core.context import owner_context

pytestmark = pytest.mark.django_db

NOW = "2026-09-16 15:00:00 +00:00"


def _log(user, provider, cost, *, key_source="global", created_at=None):
    with owner_context(user.pk):
        row = AIRequestLog.objects.create(
            user=user,
            kind="evaluate",
            provider=provider,
            model="m",
            status="ok",
            estimated_cost_usd=Decimal(cost),
            key_source=key_source,
        )
    if created_at is not None:
        AIRequestLog.all_users.filter(pk=row.pk).update(created_at=created_at)
    return row


@time_machine.travel(NOW, tick=False)
def test_usage_sums_by_month_provider_and_key_source(client_a, user_a):
    _log(user_a, "anthropic", "0.10", key_source="user")
    _log(user_a, "openai", "0.02")
    _log(user_a, "anthropic", "1.00", created_at=dt.datetime(2026, 8, 3, 12, tzinfo=dt.UTC))
    body = client_a.get("/api/v1/me/ai-usage/").json()
    assert body["month"] == {
        "starts_on": "2026-09-01",
        "anthropic_usd": 0.1,
        "openai_usd": 0.02,
        "total_usd": 0.12,
        "requests": 2,
    }
    assert body["all_time"] == {
        "anthropic_usd": 1.1,
        "openai_usd": 0.02,
        "total_usd": 1.12,
        "requests": 3,
    }
    assert body["by_key_source"] == {"user_usd": 0.1, "global_usd": 1.02}


@time_machine.travel(NOW, tick=False)
def test_usage_is_isolated_and_empty_by_default(client_a, client_b, user_a):
    _log(user_a, "anthropic", "0.50")
    assert client_a.get("/api/v1/me/ai-usage/").json()["all_time"]["requests"] == 1
    body = client_b.get("/api/v1/me/ai-usage/").json()
    assert body["all_time"] == {
        "anthropic_usd": 0.0,
        "openai_usd": 0.0,
        "total_usd": 0.0,
        "requests": 0,
    }
    assert body["month"]["starts_on"] == "2026-09-01"
    assert body["by_key_source"] == {"user_usd": 0.0, "global_usd": 0.0}
