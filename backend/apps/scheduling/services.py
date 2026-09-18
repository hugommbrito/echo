from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.conf import settings

from apps.scheduling import sm2
from apps.scheduling.models import ReviewLog, SchedulerState


def state_from_model(state: SchedulerState) -> sm2.SM2State:
    return sm2.SM2State(
        maturity=state.maturity,
        ease_factor=state.ease_factor,
        interval_days=state.interval_days,
        repetitions=state.repetitions,
        lapses=state.lapses,
        total_reviews=state.total_reviews,
        due_date=state.due_date,
        last_reviewed_on=state.last_reviewed_on,
        last_quality=state.last_quality,
    )


def apply_review(
    *, card, attempt, composite: Decimal, quality: int, reviewed_on: dt.date
) -> ReviewLog:
    """Apply SM-2 to the card for one counted attempt. Must run inside a transaction."""
    state = SchedulerState.objects.select_for_update().get(card=card)
    before = state_from_model(state)
    after = sm2.review(before, quality, reviewed_on)

    state.maturity = after.maturity
    state.ease_factor = after.ease_factor
    state.interval_days = after.interval_days
    state.repetitions = after.repetitions
    state.lapses = after.lapses
    state.total_reviews = after.total_reviews
    state.due_date = after.due_date
    state.last_reviewed_on = after.last_reviewed_on
    state.last_quality = after.last_quality
    state.save()

    return ReviewLog.objects.create(
        user_id=card.user_id,
        card=card,
        attempt=attempt,
        reviewed_on=reviewed_on,
        quality=quality,
        composite_score=composite,
        ease_before=before.ease_factor,
        ease_after=after.ease_factor,
        interval_before=before.interval_days,
        interval_after=after.interval_days,
        due_before=before.due_date,
        due_after=after.due_date,
        maturity_before=before.maturity,
        maturity_after=after.maturity,
        scheduler_version=settings.ECHO_SM2_VERSION,
    )
