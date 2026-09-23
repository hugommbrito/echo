from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.conf import settings

from apps.accounts.models import LanguageProfile
from apps.leveling import elo
from apps.leveling.models import LevelLog


def apply_level_result(*, user, card, attempt, composite: Decimal, logged_on: dt.date) -> LevelLog:
    """Move the learner's rating *in the card's language* for one counted attempt.

    Must run inside a transaction. Raises `LanguageProfile.DoesNotExist` when the profile was
    removed (only possible through the admin); the pipeline turns that into a failed stage.
    """
    profile = LanguageProfile.all_users.select_for_update().get(user=user, language=card.language)
    result = elo.apply_result(
        learner_rating=profile.level_rating,
        question_rating=card.difficulty_rating,
        composite=composite,
        counted_attempts=profile.counted_attempts,
    )
    profile.level_rating = result.rating_after
    profile.counted_attempts += 1
    profile.save(update_fields=["level_rating", "counted_attempts", "updated_at"])

    return LevelLog.objects.create(
        user=user,
        attempt=attempt,
        card=card,
        language=card.language,
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
