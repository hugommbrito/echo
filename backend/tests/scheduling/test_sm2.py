import datetime as dt
from decimal import Decimal

import pytest

from apps.scheduling import sm2

TODAY = dt.date(2026, 9, 16)


@pytest.mark.parametrize(
    "scores, composite",
    [
        ((5, 5, 5), "5.00"),
        ((1, 1, 1), "1.00"),
        ((4, 3, 3), "3.40"),
        ((3, 4, 2), "3.10"),
        ((5, 4, 3), "4.15"),
    ],
)
def test_composite_weights(scores, composite):
    assert sm2.composite_score(*scores) == Decimal(composite)


@pytest.mark.parametrize(
    "composite, structure, quality",
    [
        ("4.60", 5, 5),
        ("4.59", 5, 4),
        ("3.80", 4, 4),
        ("3.79", 4, 3),
        ("3.00", 3, 3),
        ("2.99", 3, 2),
        ("2.20", 3, 2),
        ("2.19", 3, 1),
        ("1.40", 3, 1),
        ("1.39", 3, 0),
        # structure floor: structure <= 2 caps quality at 2 (failure)
        ("4.00", 2, 2),
        ("3.50", 1, 2),
        ("2.00", 2, 1),
    ],
)
def test_quality_mapping(composite, structure, quality):
    assert sm2.quality_from_composite(Decimal(composite), structure) == quality


def test_passing_forever_grows_to_the_cap():
    state = sm2.SM2State()
    intervals, maturities = [], []
    day = TODAY
    for _ in range(7):
        state = sm2.review(state, 4, day)
        intervals.append(state.interval_days)
        maturities.append(state.maturity)
        day = state.due_date
    assert intervals == [1, 6, 15, 38, 95, 180, 180]
    assert maturities == [
        "learning",
        "learning",
        "learning",
        "mature",
        "mature",
        "mature",
        "mature",
    ]
    assert state.ease_factor == Decimal("2.50")  # quality 4 keeps the ease
    assert state.lapses == 0 and state.total_reviews == 7 and state.repetitions == 7


def test_first_review_sets_due_tomorrow_and_learning():
    state = sm2.review(sm2.SM2State(), 3, TODAY)
    assert state.due_date == TODAY + dt.timedelta(days=1)
    assert state.maturity == "learning"
    assert state.ease_factor == Decimal("2.36")


def test_failure_resets_and_counts_lapse_only_when_not_new():
    new_fail = sm2.review(sm2.SM2State(), 1, TODAY)
    assert (new_fail.interval_days, new_fail.repetitions, new_fail.lapses) == (1, 0, 0)

    mature = sm2.SM2State(
        maturity="mature", ease_factor=Decimal("2.50"), interval_days=40, repetitions=4
    )
    failed = sm2.review(mature, 2, TODAY)
    assert (failed.interval_days, failed.repetitions, failed.lapses) == (1, 0, 1)
    assert failed.maturity == "learning"
    assert failed.ease_factor == Decimal("2.18")


def test_ease_never_below_minimum():
    state = sm2.SM2State(ease_factor=Decimal("1.30"))
    for _ in range(5):
        state = sm2.review(state, 0, TODAY)
    assert state.ease_factor == Decimal("1.30")


def test_interval_uses_updated_ease():
    state = sm2.SM2State(
        maturity="learning", ease_factor=Decimal("2.50"), interval_days=6, repetitions=2
    )
    passed = sm2.review(state, 5, TODAY)
    assert passed.ease_factor == Decimal("2.60")
    assert passed.interval_days == 16  # round(6 * 2.6)
