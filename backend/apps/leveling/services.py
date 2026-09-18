from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.conf import settings

from apps.accounts.models import User
from apps.leveling import elo
from apps.leveling.models import LevelLog


def apply_level_result(
    *, user: User, card, attempt, composite: Decimal, logged_on: dt.date
) -> LevelLog:
    """Move the learner's rating for one counted attempt. Must run inside a transaction."""
    locked = User.objects.select_for_update().get(pk=user.pk)
    result = elo.apply_result(
        learner_rating=locked.level_rating,
        question_rating=card.difficulty_rating,
        composite=composite,
        counted_attempts=locked.counted_attempts,
    )
    locked.level_rating = result.rating_after
    locked.counted_attempts += 1
    locked.save(update_fields=["level_rating", "counted_attempts"])
    # keep the caller's instance in sync
    user.level_rating = locked.level_rating
    user.counted_attempts = locked.counted_attempts

    return LevelLog.objects.create(
        user=user,
        attempt=attempt,
        card=card,
        logged_on=logged_on,
        rating_before=result.rating_before,
        rating_after=result.rating_after,
        delta=result.delta,
        question_rating=result.question_rating,
        expected=result.expected,
        actual=result.actual,
        k_factor=result.k_factor,
        level_version=settings.ECHO_LEVEL_VERSION,
    )
