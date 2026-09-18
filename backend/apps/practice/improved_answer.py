from __future__ import annotations

from django.utils import timezone

from apps.ai import services as ai_services
from apps.ai.exceptions import AIError
from apps.core.exceptions import ConflictError, ServiceUnavailable
from apps.practice.models import Attempt, AttemptStatus, Evaluation


def get_or_generate_improved_answer(attempt: Attempt) -> Evaluation:
    """Generate the improved version once (on demand) and cache it on the evaluation."""
    if attempt.status != AttemptStatus.COMPLETED or not hasattr(attempt, "evaluation"):
        raise ConflictError("The attempt has not been evaluated yet.", code="not_evaluated")
    evaluation = attempt.evaluation
    if evaluation.improved_answer is not None:
        return evaluation
    if attempt.insufficient_speech:
        raise ConflictError("There was not enough speech to improve.", code="insufficient_speech")
    try:
        result = ai_services.improve_answer(
            user=attempt.user,
            card=attempt.card,
            transcript_text=attempt.transcript_text,
            issues=list(evaluation.grammar_issues or []),
            related=attempt,
        )
    except AIError as exc:
        raise ServiceUnavailable(f"Could not generate the improved answer: {exc}") from exc
    evaluation.improved_answer = result.parsed.improved_answer
    evaluation.improved_answer_notes = list(result.parsed.notes)
    evaluation.improved_answer_model = result.model
    evaluation.improved_answer_generated_at = timezone.now()
    evaluation.save(
        update_fields=[
            "improved_answer",
            "improved_answer_notes",
            "improved_answer_model",
            "improved_answer_generated_at",
            "updated_at",
        ]
    )
    return evaluation
