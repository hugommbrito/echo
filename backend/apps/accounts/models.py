from __future__ import annotations

import datetime as dt
import uuid
import zoneinfo

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone as dj_timezone

from apps.core.fields import EncryptedTextField
from apps.core.languages import LanguageCode
from apps.core.models import OwnedModel


def default_initial_rating() -> int:
    """Kept for the initial migration; the rating now lives in `LanguageProfile`."""
    return settings.ECHO_LEVEL_INITIAL_RATING


def validate_timezone(value: str) -> None:
    try:
        zoneinfo.ZoneInfo(value)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        raise ValidationError(f"Unknown timezone: {value}")


class FeedbackLanguage(models.TextChoices):
    PT_BR = "pt-BR", "Português (Brasil)"
    EN = "en", "English"


class QuestionMode(models.TextChoices):
    """How a practice question is presented: text only, spoken only, or both."""

    READ = "read", "Read"
    LISTEN = "listen", "Listen"
    BOTH = "both", "Read and listen"


def key_hint(value: str | None) -> str | None:
    """Last four characters of a secret, for display (`…a1b2`); None when unset."""
    if not value:
        return None
    return "…" + value[-4:]


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("The email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """The tenant. Every business row points to exactly one user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("e-mail", unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    timezone = models.CharField(
        max_length=64, default="America/Sao_Paulo", validators=[validate_timezone]
    )
    feedback_language = models.CharField(
        max_length=8, choices=FeedbackLanguage.choices, default=FeedbackLanguage.PT_BR
    )
    question_mode = models.CharField(
        max_length=8, choices=QuestionMode.choices, default=QuestionMode.READ
    )
    show_thinking_timer = models.BooleanField(default=True)

    # Per-user provider keys (bring your own key). Encrypted at rest; empty = use the global key.
    # Entered by the admin only; never exposed by the API (see `apps.ai.routing`).
    anthropic_api_key = EncryptedTextField(blank=True, default="")
    openai_api_key = EncryptedTextField(blank=True, default="")
    anthropic_api_key_updated_at = models.DateTimeField(null=True, blank=True)
    openai_api_key_updated_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=dj_timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.email

    # --- Time helpers -------------------------------------------------------------------
    @property
    def tzinfo(self) -> dt.tzinfo:
        try:
            return zoneinfo.ZoneInfo(self.timezone)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            return dt.UTC

    def local_now(self) -> dt.datetime:
        return dj_timezone.now().astimezone(self.tzinfo)

    def local_today(self) -> dt.date:
        return self.local_now().date()


class LanguageProfile(OwnedModel):
    """One practised language of a learner: its own ELO rating, activity flag and daily target.

    Created when the learner activates the language (self-placement A1/A2/B1); never deleted —
    pausing keeps the history and the rating.
    """

    language = models.CharField(max_length=8, choices=LanguageCode.choices)
    level_rating = models.IntegerField()
    level_rating_initial = models.IntegerField()
    counted_attempts = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    default_new_cards_per_day = models.PositiveSmallIntegerField(default=3)
    activated_at = models.DateTimeField(default=dj_timezone.now)

    class Meta(OwnedModel.Meta):
        ordering = ["activated_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "language"], name="uniq_language_profile")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.language} ({self.level_rating})"

    @property
    def level_band(self) -> str:
        from apps.leveling.elo import band_for_rating

        return band_for_rating(self.level_rating)

    @property
    def level_provisional(self) -> bool:
        from apps.leveling.elo import is_provisional

        return is_provisional(self.counted_attempts)
