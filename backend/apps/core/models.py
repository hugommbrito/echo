from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.core.context import require_current_owner_id


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OwnedQuerySet(models.QuerySet):
    pass


class OwnedManager(models.Manager.from_queryset(OwnedQuerySet)):  # type: ignore[misc]
    """Fail-closed manager: every query is scoped to the current owner or raises."""

    use_in_migrations = False

    def get_queryset(self):
        owner_id = require_current_owner_id()
        return super().get_queryset().filter(user_id=owner_id)


class OwnedModel(TimeStampedModel):
    """Base for every business model. `user` is the tenant; it is never writable by clients.

    - `objects`   -> scoped to the current owner, raises `NoOwnerContext` without one.
    - `all_users` -> deliberate global access (admin, maintenance, aggregated stats).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        editable=False,
        related_name="%(class)ss",
    )

    objects = OwnedManager()
    all_users = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.user_id is None:
            self.user_id = require_current_owner_id()
        super().save(*args, **kwargs)
