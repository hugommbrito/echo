import logging

from celery import shared_task

from apps.core.context import owner_context

log = logging.getLogger("echo.tasks")


@shared_task(name="cards.synthesize_question_audio")
def synthesize_question_audio(card_id: str, user_id: str, force: bool = False) -> bool:
    """Spoken question for one card. Failures are logged, never raised: the card works without
    audio and the lazy `GET /cards/{id}/audio/` endpoint is the retry path."""
    from apps.ai import services as ai_services
    from apps.ai.exceptions import AIError
    from apps.cards.models import Card

    with owner_context(user_id):
        card = Card.objects.select_related("user").get(pk=card_id)
        try:
            return ai_services.synthesize_question_audio(card=card, force=force)
        except AIError as exc:
            log.warning("tts for card %s failed: %s", card_id, ai_services.redact(str(exc)))
            return False
