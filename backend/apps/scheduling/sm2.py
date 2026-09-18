"""SM-2 per card (docs/PLAN.md §4.8). Pure functions over an immutable state."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

NEW, LEARNING, MATURE = "new", "learning", "mature"

QUALITY_THRESHOLDS = [
    (Decimal("4.6"), 5),
    (Decimal("3.8"), 4),
    (Decimal("3.0"), 3),
    (Decimal("2.2"), 2),
    (Decimal("1.4"), 1),
]


def composite_score(structure: int, grammar: int, fluency: int) -> Decimal:
    w = settings.ECHO_COMPOSITE_WEIGHTS
    value = (
        Decimal(str(w["structure"])) * structure
        + Decimal(str(w["grammar"])) * grammar
        + Decimal(str(w["fluency"])) * fluency
    )
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quality_from_composite(composite: Decimal, structure_score: int) -> int:
    quality = 0
    for threshold, q in QUALITY_THRESHOLDS:
        if composite >= threshold:
            quality = q
            break
    if structure_score <= settings.ECHO_STRUCTURE_FAIL_THRESHOLD:
        quality = min(quality, 2)
    return quality


@dataclass(frozen=True)
class SM2State:
    maturity: str = NEW
    ease_factor: Decimal = Decimal("2.50")
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0
    total_reviews: int = 0
    due_date: dt.date | None = None
    last_reviewed_on: dt.date | None = None
    last_quality: int | None = None


def maturity_for_interval(interval_days: int) -> str:
    return MATURE if interval_days >= settings.ECHO_SM2_MATURE_THRESHOLD_DAYS else LEARNING


def next_ease(ease: Decimal, quality: int) -> Decimal:
    q = Decimal(5 - quality)
    ease = ease + (Decimal("0.1") - q * (Decimal("0.08") + q * Decimal("0.02")))
    ease = max(Decimal(str(settings.ECHO_SM2_MIN_EASE)), ease)
    return ease.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def review(state: SM2State, quality: int, today: dt.date) -> SM2State:
    if not 0 <= quality <= 5:
        raise ValueError("quality must be in 0..5")
    ease = next_ease(state.ease_factor, quality)
    lapses = state.lapses
    if quality < 3:
        repetitions = 0
        interval = 1
        if state.maturity != NEW:
            lapses += 1
    else:
        if state.repetitions == 0:
            interval = 1
        elif state.repetitions == 1:
            interval = 6
        else:
            interval = int(
                (Decimal(state.interval_days) * ease).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        repetitions = state.repetitions + 1
    interval = max(1, min(interval, settings.ECHO_SM2_MAX_INTERVAL_DAYS))
    return replace(
        state,
        maturity=maturity_for_interval(interval),
        ease_factor=ease,
        interval_days=interval,
        repetitions=repetitions,
        lapses=lapses,
        total_reviews=state.total_reviews + 1,
        due_date=today + dt.timedelta(days=interval),
        last_reviewed_on=today,
        last_quality=quality,
    )
