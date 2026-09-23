"""Each practised language has its own ELO rating, K factor and log."""

import datetime as dt
from decimal import Decimal

import pytest

from apps.accounts.models import LanguageProfile
from apps.core.context import owner_context
from apps.leveling.models import LevelLog
from apps.leveling.services import apply_level_result
from apps.practice.models import Attempt

pytestmark = pytest.mark.django_db


def _attempt(user, card, number=1):
    with owner_context(user.pk):
        return Attempt.objects.create(
            user=user,
            card=card,
            attempt_number=number,
            attempted_on=dt.date(2026, 9, 16),
            audio_mime="audio/webm",
            status="completed",
        )


def test_french_attempt_moves_only_the_french_rating(user_a, make_card, make_profile):
    en = LanguageProfile.all_users.get(user=user_a, language="en")
    en.counted_attempts = 150  # long history: K = 16
    en.save()
    make_profile(user_a, "fr", starting_level="A1")
    fr_card = make_card(user_a, question="Parlez-moi de vous.", level="A1", language="fr")
    attempt = _attempt(user_a, fr_card)

    with owner_context(user_a.pk):
        log = apply_level_result(
            user=user_a,
            card=fr_card,
            attempt=attempt,
            composite=Decimal("4.20"),
            logged_on=dt.date(2026, 9, 16),
        )
    assert log.language == "fr" and log.k_factor == 40  # fresh French profile: provisional K
    assert log.rating_before == 900 and log.delta > 0

    fr = LanguageProfile.all_users.get(user=user_a, language="fr")
    assert fr.level_rating == log.rating_after and fr.counted_attempts == 1
    en.refresh_from_db()
    assert en.level_rating == 1150 and en.counted_attempts == 150

    en_card = make_card(user_a, question="Tell me about yourself.", level="A2", language="en")
    with owner_context(user_a.pk):
        en_log = apply_level_result(
            user=user_a,
            card=en_card,
            attempt=_attempt(user_a, en_card),
            composite=Decimal("4.20"),
            logged_on=dt.date(2026, 9, 16),
        )
    assert en_log.language == "en" and en_log.k_factor == 16
    with owner_context(user_a.pk):
        assert sorted(LevelLog.objects.values_list("language", flat=True)) == ["en", "fr"]


def test_missing_profile_fails_the_scheduling_stage(
    client_a, user_a, make_card, make_profile, audio_file
):
    from apps.ai.clients.fake import FakeTranscriber

    make_profile(user_a, "fr")
    card = make_card(user_a, question="Décrivez votre quartier.", level="A1", language="fr")
    LanguageProfile.all_users.filter(user=user_a, language="fr").delete()
    FakeTranscriber.queue("Alors, mon quartier est calme, il y a un parc et une épicerie.")
    accepted = client_a.post(
        "/api/v1/attempts/",
        {"card_id": str(card.id), "audio": audio_file(), "mime_type": "audio/webm"},
        format="multipart",
    )
    body = client_a.get(f"/api/v1/attempts/{accepted.json()['id']}/").json()
    assert body["status"] == "failed" and body["failure_stage"] == "scheduling"
    assert "No language profile" in body["error_message"]
    assert body["evaluation"] is not None  # the evaluation was kept for the retry
