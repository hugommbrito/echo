"""Adaptive level, ELO-style (docs/PLAN.md §4.7). Pure functions; parameters come from settings.

- The learner has a rating S; each question has a rating Q (band centre + difficulty offset).
- Expected result  E = 1 / (1 + 10^((Q - S) / 400)).
- Actual result    A = (composite - 1) / 4 in [0, 1]; composite 3 ("at the level") => 0.5.
- Delta            dS = round(K * (A - E)), K by number of counted attempts (40 -> 24 -> 16).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _bands() -> list[dict]:
    return settings.ECHO_LEVEL_BANDS


def band_for_rating(rating: int) -> str:
    for band in _bands():
        if band["min"] <= rating <= band["max"]:
            return band["label"]
    return _bands()[-1]["label"] if rating > _bands()[-1]["max"] else _bands()[0]["label"]


def rating_for_level(level: str, difficulty: str = "typical") -> int:
    """Rating of a question: centre of the requested band + difficulty offset."""
    for band in _bands():
        if band["label"] == level:
            return band["center"] + settings.ECHO_LEVEL_DIFFICULTY_OFFSETS[difficulty]
    raise ValueError(f"Unknown CEFR level: {level}")


def shift_level(level: str, steps: int) -> str | None:
    """Level `steps` bands away, or None when it would leave the scale."""
    index = LEVEL_ORDER.index(level) + steps
    if 0 <= index < len(LEVEL_ORDER):
        return LEVEL_ORDER[index]
    return None


def bands_for_api() -> list[dict]:
    return [
        {"label": b["label"], "min": b["min"], "max": b["max"], "center": b["center"]}
        for b in _bands()
    ]


def expected_score(learner_rating: int, question_rating: int) -> Decimal:
    value = 1 / (1 + 10 ** ((question_rating - learner_rating) / 400))
    return Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def actual_from_composite(composite: Decimal | float) -> Decimal:
    value = (Decimal(str(composite)) - 1) / 4
    value = max(Decimal(0), min(Decimal(1), value))
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def k_for(counted_attempts: int) -> int:
    """K factor for the *next* counted attempt given how many were counted so far."""
    for upper, k in settings.ECHO_LEVEL_K_SCHEDULE:
        if upper is None or counted_attempts < upper:
            return k
    return settings.ECHO_LEVEL_K_SCHEDULE[-1][1]


def is_provisional(counted_attempts: int) -> bool:
    first_threshold = settings.ECHO_LEVEL_K_SCHEDULE[0][0]
    return first_threshold is not None and counted_attempts < first_threshold


def _round_half_away(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def clamp_rating(rating: int) -> int:
    return max(settings.ECHO_LEVEL_RATING_MIN, min(settings.ECHO_LEVEL_RATING_MAX, rating))


@dataclass(frozen=True)
class LevelResult:
    rating_before: int
    rating_after: int
    delta: int
    expected: Decimal
    actual: Decimal
    question_rating: int
    k_factor: int

    @property
    def band_before(self) -> str:
        return band_for_rating(self.rating_before)

    @property
    def band_after(self) -> str:
        return band_for_rating(self.rating_after)


def apply_result(
    learner_rating: int,
    question_rating: int,
    composite: Decimal | float,
    counted_attempts: int,
) -> LevelResult:
    expected = expected_score(learner_rating, question_rating)
    actual = actual_from_composite(composite)
    k = k_for(counted_attempts)
    # Use the unrounded expectation for the delta so rounding happens once.
    raw_expected = Decimal(str(1 / (1 + 10 ** ((question_rating - learner_rating) / 400))))
    delta = _round_half_away(Decimal(k) * (actual - raw_expected))
    rating_after = clamp_rating(learner_rating + delta)
    return LevelResult(
        rating_before=learner_rating,
        rating_after=rating_after,
        delta=rating_after - learner_rating,
        expected=expected,
        actual=actual,
        question_rating=question_rating,
        k_factor=k,
    )
