from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.languages import LanguageCode
from apps.core.models import OwnedModel, TimeStampedModel


class CEFRLevel(models.TextChoices):
    A1 = "A1", "A1"
    A2 = "A2", "A2"
    B1 = "B1", "B1"
    B2 = "B2", "B2"
    C1 = "C1", "C1"
    C2 = "C2", "C2"


LEVEL_ORDER: list[str] = [level.value for level in CEFRLevel]


class Probe(models.TextChoices):
    NONE = "none", "None"
    ABOVE = "above", "One level above"
    BELOW = "below", "One level below"


class CardStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    ARCHIVED = "archived", "Archived"


class CardSource(models.TextChoices):
    GENERATED = "generated", "Generated"
    MANUAL = "manual", "Manual"


class CategoryQuerySet(models.QuerySet):
    def visible_to(self, user):
        return self.filter(Q(owner__isnull=True) | Q(owner=user))

    def active(self):
        return self.filter(is_active=True)


class Category(TimeStampedModel):
    """Global (owner NULL, maintained by the admin) or personal (owner = the user).

    Deliberately not an `OwnedModel`: global rows have no owner.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    slug = models.SlugField(max_length=60)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    generation_hint = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.SmallIntegerField(default=0)

    objects = CategoryQuerySet.as_manager()

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                fields=["slug"], condition=Q(owner__isnull=True), name="uniq_global_category_slug"
            ),
            models.UniqueConstraint(fields=["owner", "slug"], name="uniq_personal_category_slug"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def scope(self) -> str:
        return "global" if self.owner_id is None else "personal"

    def is_visible_to(self, user) -> bool:
        return self.owner_id is None or self.owner_id == user.pk


class Card(OwnedModel):
    """One generated question. `question_text` is immutable once created."""

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="cards")
    language = models.CharField(max_length=8, choices=LanguageCode.choices)
    question_text = models.TextField()
    scenario = models.TextField(null=True, blank=True)
    key_points = models.JSONField(default=list, blank=True)
    cefr_level = models.CharField(max_length=2, choices=CEFRLevel.choices)
    difficulty_rating = models.IntegerField()
    probe = models.CharField(max_length=8, choices=Probe.choices, default=Probe.NONE)
    status = models.CharField(max_length=10, choices=CardStatus.choices, default=CardStatus.ACTIVE)
    source = models.CharField(
        max_length=10, choices=CardSource.choices, default=CardSource.GENERATED
    )
    created_in_session = models.ForeignKey(
        "practice.DailySession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_cards",
    )
    generation_model = models.CharField(max_length=80, blank=True)
    prompt_version = models.CharField(max_length=20, blank=True)

    class Meta(OwnedModel.Meta):
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "cefr_level"]),
            models.Index(fields=["user", "language"]),
        ]

    def __str__(self) -> str:
        return self.question_text[:80]
