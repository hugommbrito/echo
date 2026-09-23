"""The pipeline transcribes and evaluates in the card's language."""

import pytest
import time_machine

from apps.ai.clients.fake import FakeLLM, FakeTranscriber
from apps.ai.models import AIRequestLog
from apps.core.context import owner_context

pytestmark = pytest.mark.django_db

NOON_UTC = "2026-09-16 15:00:00 +00:00"


@time_machine.travel(NOON_UTC, tick=False)
def test_french_card_runs_the_pipeline_in_french(
    client_a, user_a, make_card, make_profile, audio_file, global_categories
):
    make_profile(user_a, "fr")
    card = make_card(
        user_a,
        global_categories["shopping"],
        question="Racontez-moi la dernière fois que vous avez magasiné.",
        level="A1",
        language="fr",
        difficulty_rating=900,
    )
    accepted = client_a.post(
        "/api/v1/attempts/",
        {"card_id": str(card.id), "audio": audio_file(), "mime_type": "audio/webm"},
        format="multipart",
    )
    body = client_a.get(f"/api/v1/attempts/{accepted.json()['id']}/").json()
    assert body["status"] == "completed", body
    assert body["language"] == "fr"
    assert body["transcript_text"].startswith("Alors, euh")  # the fake's French default
    assert FakeTranscriber.calls[-1]["language"] == "fr"
    assert "euh" in FakeTranscriber.calls[-1]["prompt"].lower()
    evaluate_call = [c for c in FakeLLM.calls if c["output_format"] == "EvaluationOutput"][-1]
    assert "FLE teacher" in evaluate_call["system"]
    assert body["evaluation"]["fluency"]["markers"]["fillers"] >= 1
    assert body["level_change"]["rating_before"] == 900
    with owner_context(user_a.pk):
        rows = list(AIRequestLog.objects.order_by("created_at").values_list("kind", "language"))
        assert rows == [("transcribe", "fr"), ("evaluate", "fr")]
        from apps.practice.models import Evaluation

        assert Evaluation.objects.get(attempt_id=body["id"]).prompt_version == "v2"

    improved = client_a.post(f"/api/v1/attempts/{body['id']}/improved-answer/")
    assert improved.status_code == 200
    improve_call = FakeLLM.calls[-1]
    assert "Canadian French (Québec) one step above A1" in improve_call["system"]
    with owner_context(user_a.pk):
        assert AIRequestLog.objects.get(kind="improve_answer").language == "fr"
