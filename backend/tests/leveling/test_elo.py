from decimal import Decimal

import pytest

from apps.leveling import elo


@pytest.mark.parametrize(
    "rating, band",
    [
        (599, "A1"),
        (999, "A1"),
        (1000, "A2"),
        (1150, "A2"),
        (1199, "A2"),
        (1200, "B1"),
        (1399, "B1"),
        (1400, "B2"),
        (1599, "B2"),
        (1600, "C1"),
        (1799, "C1"),
        (1800, "C2"),
        (2200, "C2"),
    ],
)
def test_band_for_rating(rating, band):
    assert elo.band_for_rating(rating) == band


@pytest.mark.parametrize(
    "level, difficulty, rating",
    [
        ("A1", "typical", 900),
        ("A2", "typical", 1100),
        ("B1", "easier", 1240),
        ("B1", "typical", 1300),
        ("B1", "harder", 1360),
        ("B2", "typical", 1500),
        ("C1", "typical", 1700),
        ("C2", "typical", 1900),
    ],
)
def test_rating_for_level(level, difficulty, rating):
    assert elo.rating_for_level(level, difficulty) == rating


def test_shift_level_edges():
    assert elo.shift_level("A2", 1) == "B1"
    assert elo.shift_level("A2", -1) == "A1"
    assert elo.shift_level("A1", -1) is None
    assert elo.shift_level("C2", 1) is None


@pytest.mark.parametrize(
    "counted, k", [(0, 40), (19, 40), (20, 24), (99, 24), (100, 16), (5000, 16)]
)
def test_k_schedule(counted, k):
    assert elo.k_for(counted) == k


def test_provisional_until_first_threshold():
    assert elo.is_provisional(0) and elo.is_provisional(19) and not elo.is_provisional(20)


# Table from docs/PLAN.md §4.7.4 — S = 1150, K = 40.
@pytest.mark.parametrize(
    "question_rating, composite, expected, actual, delta",
    [
        (1500, "4.2", "0.118", "0.800", 27),
        (1300, "4.2", "0.297", "0.800", 20),
        (1300, "2.0", "0.297", "0.250", -2),
        (1100, "3.0", "0.571", "0.500", -3),
        (900, "4.6", "0.808", "0.900", 4),
        (900, "1.8", "0.808", "0.200", -24),
    ],
)
def test_plan_examples(question_rating, composite, expected, actual, delta):
    result = elo.apply_result(1150, question_rating, Decimal(composite), counted_attempts=0)
    assert result.expected == Decimal(expected)
    assert result.actual == Decimal(actual)
    assert result.delta == delta
    assert result.rating_after == 1150 + delta
    assert result.k_factor == 40


def test_neutral_result_at_equal_ratings():
    result = elo.apply_result(1300, 1300, Decimal("3.0"), counted_attempts=50)
    assert result.expected == Decimal("0.500") and result.delta == 0 and result.k_factor == 24


def test_rating_is_clamped():
    top = elo.apply_result(2195, 1900, Decimal("5.0"), 0)
    assert top.rating_after == 2200 and top.delta == 5
    bottom = elo.apply_result(605, 900, Decimal("1.0"), 0)
    assert bottom.rating_after == 600 and bottom.delta == -5


def test_actual_is_bounded():
    assert elo.actual_from_composite(Decimal("1.0")) == Decimal("0.000")
    assert elo.actual_from_composite(Decimal("5.0")) == Decimal("1.000")
