"""Explicit per-request tenant scoping for DRF views (on top of the fail-closed manager)."""

from __future__ import annotations

from apps.core.models import OwnedModel


class OwnedQuerySetMixin:
    """Every DRF view that exposes an `OwnedModel` must use this mixin.

    Subclasses set `model`. `get_queryset()` is scoped to `request.user`, so lookups by UUID
    from another user resolve to 404. `perform_create()` injects the owner; serializers never
    accept `user` from the client (the field is `editable=False`).
    """

    model: type[OwnedModel]

    def get_base_queryset(self):
        return self.model.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.model.all_users.none()
        return self.get_base_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
