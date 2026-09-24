"""Thinking-time baseline, zones and clamping (`apps.practice.thinking_time`)."""

import datetime as dt
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile

from apps.core.context import no_owner_context, owner_context
from apps.practice import thinking_time
from apps.practice.models import Attempt

pytestmark = pytest.mark.django_db


def _attempt(user, card, thinking, *, status="completed"):
    with owner_context(user.pk):
        number = Attempt.objects.filter(card=card).count() + 1
        attempt = Attempt(
            user=user,
            card=card,
            attempt_number=number,
            attempted_on=dt.date(2026, 9, 16),
            audio_mime="audio/webm",
            audio_size_bytes=10,
            status=status,
            thinking_seconds=Decimal(str(thinking)) if thinking is not None else None,
        )
        attempt.audio_file.save(f"{attempt.id}.webm", ContentFile(b"x"), save=False)
        attempt.save()
    return attempt


def test_default_baseline_below_min_samples(user_a, make_card):
    card = make_card(user_a)
    for value in (4, 5, 6, 20):
        _attempt(user_a, card, value)
    baseline = thinking_time.baseline_for_language(user_a, "en")
    assert baseline.as_dict() == {"baseline_seconds": 6.0, "samples": 4, "is_default": True}


def test_median_of_recent_attempts_within_the_window(user_a, make_card, settings):
    card = make_card(user_a)
    for value in (4, 5, 6, 20, 30):
        _attempt(user_a, card, value)
    baseline = thinking_time.baseline_for_language(user_a, "en")
    assert baseline.as_dict() == {"baseline_seconds": 6.0, "samples": 5, "is_default": False}

    settings.ECHO_THINKING_BASELINE_WINDOW = 3
    settings.ECHO_THINKING_BASELINE_MIN_SAMPLES = 3
    for value in (2, 4, 8):  # newest three
        _attempt(user_a, card, value)
    baseline = thinking_time.baseline_for_language(user_a, "en")
    assert baseline.baseline_seconds == Decimal("4.00") and baseline.samples == 3
    newest = Attempt.all_users.filter(user=user_a).order_by("-created_at").first()
    excluded = thinking_time.baseline_for_language(user_a, "en", exclude_attempt_id=newest.pk)
    assert excluded.baseline_seconds == Decimal("4.00")  # median of (30, 2, 4)
    assert [
        float(v)
        for v in thinking_time.recent_thinking_times(user_a, "en", exclude_attempt_id=newest.pk)
    ] == [4.0, 2.0, 30.0]


def test_only_completed_attempts_with_a_time_in_the_same_language_count(
    user_a, make_card, make_profile, settings
):
    settings.ECHO_THINKING_BASELINE_MIN_SAMPLES = 1
    en, fr = make_card(user_a, language="en"), make_card(user_a, language="fr")
    make_profile(user_a, "fr")
    _attempt(user_a, en, 10)
    _attempt(user_a, en, None)
    _attempt(user_a, en, 100, status="failed")
    _attempt(user_a, en, 200, status="uploaded")
    _attempt(user_a, fr, 50)
    assert thinking_time.baseline_for_language(user_a, "en").baseline_seconds == Decimal("10.00")
    assert thinking_time.baseline_for_language(user_a, "fr").baseline_seconds == Decimal("50.00")


def test_baseline_works_without_an_owner_context_and_per_user(user_a, user_b, make_card, settings):
    settings.ECHO_THINKING_BASELINE_MIN_SAMPLES = 1
    _attempt(user_a, make_card(user_a), 3)
    with no_owner_context():
        assert thinking_time.baseline_for_language(user_a, "en").baseline_seconds == Decimal("3.00")
        assert thinking_time.baseline_for_language(user_b, "en").is_default is True


def test_zones_have_no_lower_bound():
    assert thinking_time.zone(0, 6) == "green"
    assert thinking_time.zone(6, 6) == "green"
    assert thinking_time.zone(9, 6) == "yellow"
    assert thinking_time.zone(9.01, 6) == "red"
    assert thinking_time.zone(100, 0) == "green"  # no reference -> never penalised


def test_clamp():
    assert thinking_time.clamp_thinking_seconds(None) is None
    assert thinking_time.clamp_thinking_seconds("-1") == Decimal("0.00")
    assert thinking_time.clamp_thinking_seconds(5000) == Decimal("900.00")
    assert thinking_time.clamp_thinking_seconds("7.554") == Decimal("7.55")
