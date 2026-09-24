"""Spoken question (TTS): storage, telemetry, idempotency and failure isolation."""

from decimal import Decimal

import pytest

from apps.ai import pricing
from apps.ai import services as ai_services
from apps.ai.clients.fake import FakeProbe, FakeTTS
from apps.ai.exceptions import AudioProbeError, SpeechSynthesisError
from apps.ai.models import AIRequestLog
from apps.core.context import owner_context

pytestmark = pytest.mark.django_db


def test_synthesize_stores_the_audio_and_logs_the_call(user_a, make_card):
    card = make_card(user_a, question="Tell me about your last trip.")
    FakeProbe.queue(4.5)
    with owner_context(user_a.pk):
        assert ai_services.synthesize_question_audio(card=card) is True
        card.refresh_from_db()
        assert card.question_audio.name == f"users/{user_a.id}/cards/{card.id}.mp3"
        assert card.question_audio_seconds == Decimal("4.50")
        assert card.question_audio_model == "gpt-4o-mini-tts"
        assert card.question_audio_voice == "marin"
        row = AIRequestLog.objects.get(kind="tts")
    assert row.language == "en" and row.status == "ok" and row.key_source == "global"
    assert row.audio_seconds == Decimal("4.50")
    assert row.estimated_cost_usd == pricing.tts_cost("gpt-4o-mini-tts", 4.5) > 0
    assert row.related_object_type == "Card" and row.related_object_id == card.id
    call = FakeTTS.calls[-1]
    assert call["text"] == "Tell me about your last trip." and call["voice"] == "marin"
    assert "Canada" in call["instructions"] and call["response_format"] == "mp3"


def test_french_cards_use_the_french_voice(user_a, make_card):
    card = make_card(user_a, language="fr", question="Parlez-moi de vous.")
    with owner_context(user_a.pk):
        ai_services.synthesize_question_audio(card=card)
    call = FakeTTS.calls[-1]
    assert call["voice"] == "cedar" and "Québec" in call["instructions"]
    with owner_context(user_a.pk):
        assert AIRequestLog.objects.get(kind="tts").language == "fr"


def test_synthesize_is_idempotent_unless_forced(user_a, make_card):
    card = make_card(user_a)
    with owner_context(user_a.pk):
        assert ai_services.synthesize_question_audio(card=card) is True
        assert ai_services.synthesize_question_audio(card=card) is False
        assert len(FakeTTS.calls) == 1 and AIRequestLog.objects.filter(kind="tts").count() == 1
        name = card.question_audio.name
        assert ai_services.synthesize_question_audio(card=card, force=True) is True
        card.refresh_from_db()
        assert card.question_audio.name == name  # replaced in place, no "_hash" suffix
        assert len(FakeTTS.calls) == 2 and AIRequestLog.objects.filter(kind="tts").count() == 2


def test_failure_is_logged_and_the_card_stays_usable(user_a, make_card):
    card = make_card(user_a)
    FakeTTS.fail_next = SpeechSynthesisError("tts down sk-proj-leak1234567")
    with owner_context(user_a.pk):
        with pytest.raises(SpeechSynthesisError):
            ai_services.synthesize_question_audio(card=card)
        card.refresh_from_db()
        assert not card.question_audio and card.question_audio_seconds is None
        row = AIRequestLog.objects.get(kind="tts")
    assert row.status == "error" and "leak1234567" not in row.error and "sk-…" in row.error


def test_unmeasurable_audio_is_still_stored(user_a, make_card):
    card = make_card(user_a)
    FakeProbe.queue(AudioProbeError("cannot read"))
    with owner_context(user_a.pk):
        assert ai_services.synthesize_question_audio(card=card) is True
        card.refresh_from_db()
        assert card.question_audio and card.question_audio_seconds is None
        assert AIRequestLog.objects.get(kind="tts").audio_seconds is None


def test_tts_uses_the_users_own_openai_key_when_present(user_a, make_card):
    user_a.openai_api_key = "sk-proj-own-tts-key-0001"
    user_a.save()
    card = make_card(user_a)
    with owner_context(user_a.pk):
        ai_services.synthesize_question_audio(card=card)
        assert AIRequestLog.objects.get(kind="tts").key_source == "user"
