"""Generated cards get a spoken question; the lazy endpoint covers the rest."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.ai.clients.fake import FakeTTS
from apps.ai.exceptions import SpeechSynthesisError
from apps.ai.models import AIRequestLog
from apps.cards.models import Card
from apps.core.context import owner_context

pytestmark = pytest.mark.django_db


def _session(client, category, count=2):
    return client.post(
        "/api/v1/sessions/",
        {"category_ids": [str(category.id)], "new_cards_targets": {"en": count}},
        format="json",
    ).json()


def test_generated_cards_come_with_audio(client_a, user_a, global_categories):
    session = _session(client_a, global_categories["travel"])
    assert session["status"] == "ready"
    queue = client_a.get(f"/api/v1/sessions/{session['id']}/queue/").json()
    assert len(queue) == 2
    for item in queue:
        card = item["card"]
        assert card["question_audio_url"].startswith(f"/media/users/{user_a.id}/cards/{card['id']}")
        assert isinstance(card["question_audio_seconds"], float)
    assert len(FakeTTS.calls) == 2
    assert {c["text"] for c in FakeTTS.calls} == {i["card"]["question_text"] for i in queue}
    with owner_context(user_a.pk):
        assert AIRequestLog.objects.filter(kind="tts", status="ok").count() == 2


def test_tts_failure_never_blocks_generation(client_a, user_a, global_categories):
    FakeTTS.fail_next = SpeechSynthesisError("tts down")
    session = _session(client_a, global_categories["travel"])
    assert session["status"] == "ready" and session["plans"][0]["generated_count"] == 2
    queue = client_a.get(f"/api/v1/sessions/{session['id']}/queue/").json()
    urls = [item["card"]["question_audio_url"] for item in queue]
    assert urls.count(None) == 1 and len(urls) == 2
    with owner_context(user_a.pk):
        statuses = sorted(AIRequestLog.objects.filter(kind="tts").values_list("status", flat=True))
    assert statuses == ["error", "ok"]


def test_audio_endpoint_synthesises_on_demand_then_redirects(client_a, user_a, make_card):
    card = make_card(user_a)
    assert client_a.get(f"/api/v1/cards/{card.id}/").json()["question_audio_url"] is None
    response = client_a.get(f"/api/v1/cards/{card.id}/audio/")
    assert response.status_code == 302, response.content
    assert f"users/{user_a.id}/cards/{card.id}" in response["Location"]
    assert response["Cache-Control"] == "private, no-store"
    assert len(FakeTTS.calls) == 1
    again = client_a.get(f"/api/v1/cards/{card.id}/audio/")
    assert again.status_code == 302 and len(FakeTTS.calls) == 1  # already stored, no new call
    detail = client_a.get(f"/api/v1/cards/{card.id}/").json()
    assert detail["question_audio_url"] and detail["question_audio_seconds"] == 30.0


def test_audio_endpoint_reports_provider_failures_and_isolation(
    client_a, client_b, user_a, make_card
):
    card = make_card(user_a)
    FakeTTS.fail_next = SpeechSynthesisError("tts down")
    failed = client_a.get(f"/api/v1/cards/{card.id}/audio/")
    assert failed.status_code == 503 and failed.json()["code"] == "service_unavailable"
    assert client_b.get(f"/api/v1/cards/{card.id}/audio/").status_code == 404


def test_backfill_command(user_a, make_card):
    active = make_card(user_a, question="Active one")
    make_card(user_a, question="Suspended one", status="suspended")
    out = StringIO()
    call_command("synthesize_card_audio", "--dry-run", stdout=out)
    assert "1 card(s) to process" in out.getvalue() and len(FakeTTS.calls) == 0
    out = StringIO()
    call_command("synthesize_card_audio", "--sync", stdout=out)
    assert "synthesised=1 failed=0" in out.getvalue()
    assert Card.all_users.get(pk=active.pk).question_audio
    assert not Card.all_users.get(question_text="Suspended one").question_audio
    out = StringIO()
    call_command("synthesize_card_audio", stdout=out)  # nothing left (eager task otherwise)
    assert "0 card(s) to process" in out.getvalue()
