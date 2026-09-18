from __future__ import annotations

import datetime as dt
import uuid
import zoneinfo

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone as dj_timezone


def default_initial_rating() -> int:
    return settings.ECHO_LEVEL_INITIAL_RATING


def validate_timezone(value: str) -> None:
    try:
        zoneinfo.ZoneInfo(value)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        raise ValidationError(f"Unknown timezone: {value}")


class FeedbackLanguage(models.TextChoices):
    PT_BR = "pt-BR", "Português (Brasil)"
    EN = "en", "English"


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
    default_new_cards_per_day = models.PositiveSmallIntegerField(default=3)

    level_rating = models.IntegerField(default=default_initial_rating)
    level_rating_initial = models.IntegerField(null=True, blank=True)
    counted_attempts = models.PositiveIntegerField(default=0)

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

    def save(self, *args, **kwargs):
        if self.level_rating_initial is None:
            self.level_rating_initial = self.level_rating
        super().save(*args, **kwargs)

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

    # --- Level helpers ------------------------------------------------------------------
    @property
    def level_band(self) -> str:
        from apps.leveling.elo import band_for_rating

        return band_for_rating(self.level_rating)

    @property
    def level_provisional(self) -> bool:
        from apps.leveling.elo import is_provisional

        return is_provisional(self.counted_attempts)
