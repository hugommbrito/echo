"""Thinking time: seconds between the question being shown and the first press on "record".

The reference is the learner's own recent history per language (median of the last N attempts
with a measured time). Below `ECHO_THINKING_BASELINE_MIN_SAMPLES` a fixed default applies.
Zones: green <= 1.0x the reference, yellow <= `ECHO_THINKING_YELLOW_RATIO`x, red above; there is
no lower bound (faster is never penalised). Never part of the composite score, SM-2 or the rating.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from django.conf import settings

from apps.practice.models import Attempt, AttemptStatus

ZONE_GREEN = "green"
ZONE_YELLOW = "yellow"
ZONE_RED = "red"


@dataclass(frozen=True)
class ThinkingBaseline:
    baseline_seconds: Decimal
    samples: int
    is_default: bool

    def as_dict(self) -> dict:
        return {
            "baseline_seconds": float(self.baseline_seconds),
            "samples": self.samples,
            "is_default": self.is_default,
        }


def recent_thinking_times(user, language: str, *, exclude_attempt_id=None) -> list[Decimal]:
    """Newest first. `all_users` on purpose: `/me/` is serialised at login, before any owner
    context exists, and the pipeline runs inside the worker's context anyway."""
    qs = Attempt.all_users.filter(
        user=user,
        card__language=language,
        status=AttemptStatus.COMPLETED,
        thinking_seconds__isnull=False,
    )
    if exclude_attempt_id is not None:
        qs = qs.exclude(pk=exclude_attempt_id)
    window = settings.ECHO_THINKING_BASELINE_WINDOW
    return list(qs.order_by("-created_at").values_list("thinking_seconds", flat=True)[:window])


def baseline_for_language(user, language: str, *, exclude_attempt_id=None) -> ThinkingBaseline:
    values = recent_thinking_times(user, language, exclude_attempt_id=exclude_attempt_id)
    if len(values) < settings.ECHO_THINKING_BASELINE_MIN_SAMPLES:
        return ThinkingBaseline(
            Decimal(settings.ECHO_THINKING_DEFAULT_BASELINE_SECONDS), len(values), True
        )
    return ThinkingBaseline(
        Decimal(str(median(values))).quantize(Decimal("0.01")), len(values), False
    )


def zone(seconds, baseline_seconds) -> str:
    value = Decimal(str(seconds))
    baseline = Decimal(str(baseline_seconds))
    if baseline <= 0 or value <= baseline:
        return ZONE_GREEN
    if value <= baseline * Decimal(str(settings.ECHO_THINKING_YELLOW_RATIO)):
        return ZONE_YELLOW
    return ZONE_RED


def clamp_thinking_seconds(value) -> Decimal | None:
    """Server-side sanity: never negative, never above `ECHO_THINKING_MAX_SECONDS`, 2 decimals."""
    if value is None:
        return None
    seconds = Decimal(str(value))
    seconds = max(Decimal(0), min(seconds, Decimal(settings.ECHO_THINKING_MAX_SECONDS)))
    return seconds.quantize(Decimal("0.01"))
