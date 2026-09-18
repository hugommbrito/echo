import logging

from celery import shared_task

from apps.core.context import owner_context

log = logging.getLogger("echo.tasks")


@shared_task(name="practice.generate_session_cards")
def generate_session_cards(session_id: str, user_id: str) -> int:
    from apps.practice.models import DailySession
    from apps.practice.services import run_generation

    with owner_context(user_id):
        session = DailySession.objects.select_related("user").get(pk=session_id)
        created = run_generation(session)
        log.info("session %s: generated %d cards", session_id, len(created))
        return len(created)


@shared_task(name="practice.process_attempt")
def process_attempt(attempt_id: str, user_id: str) -> str:
    from apps.practice import pipeline

    with owner_context(user_id):
        attempt = pipeline.run(attempt_id)
        return attempt.status
