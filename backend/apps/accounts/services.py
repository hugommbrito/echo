"""Language profiles: activation (self-placement), pause/resume and lookups.

Profiles are read with `all_users.filter(user=...)` on purpose: the login response is built
before the owner context exists, and admin/commands run outside any request.
"""

from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, ValidationError

from apps.accounts.models import LanguageProfile
from apps.core.exceptions import ConflictError
from apps.core.languages import is_known_language
from apps.leveling.elo import rating_for_level


def all_profiles(user):
    """Profiles in a stable order (language code) so every list in the API agrees."""
    return LanguageProfile.all_users.filter(user=user).order_by("language")


def active_profiles(user):
    return all_profiles(user).filter(is_active=True)


def active_language_codes(user) -> list[str]:
    return list(active_profiles(user).values_list("language", flat=True))


def get_profile(user, language: str) -> LanguageProfile:
    profile = all_profiles(user).filter(language=language).first()
    if profile is None:
        raise NotFound(f"No profile for language {language!r}.", code="no_language_profile")
    return profile


def activate_language(user, *, language: str, starting_level: str | None = None) -> LanguageProfile:
    if not is_known_language(language):
        raise ValidationError(
            {"language": [f"Unknown language: {language}"]}, code="unknown_language"
        )
    starting_level = starting_level or settings.ECHO_SELF_PLACEMENT_DEFAULT_LEVEL
    if starting_level not in settings.ECHO_SELF_PLACEMENT_LEVELS:
        raise ValidationError(
            {
                "starting_level": [
                    f"Choose one of {', '.join(settings.ECHO_SELF_PLACEMENT_LEVELS)}."
                ]
            },
            code="invalid_starting_level",
        )
    if all_profiles(user).filter(language=language).exists():
        raise ConflictError("This language is already activated.", code="language_exists")
    rating = rating_for_level(starting_level)
    try:
        with transaction.atomic():
            return LanguageProfile.all_users.create(
                user=user,
                language=language,
                level_rating=rating,
                level_rating_initial=rating,
                counted_attempts=0,
                is_active=True,
                default_new_cards_per_day=3,
            )
    except IntegrityError:  # two concurrent activations
        raise ConflictError("This language is already activated.", code="language_exists")


def update_language_profile(
    profile: LanguageProfile,
    *,
    is_active: bool | None = None,
    default_new_cards_per_day: int | None = None,
) -> LanguageProfile:
    fields = ["updated_at"]
    if is_active is not None:
        profile.is_active = is_active
        fields.append("is_active")
    if default_new_cards_per_day is not None:
        profile.default_new_cards_per_day = default_new_cards_per_day
        fields.append("default_new_cards_per_day")
    profile.save(update_fields=fields)
    return profile
