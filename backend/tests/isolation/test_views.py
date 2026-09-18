"""Every DRF view exposing an OwnedModel must use OwnedQuerySetMixin."""

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.views import APIView

from apps.accounts.scoping import OwnedQuerySetMixin
from apps.core.models import OwnedModel


def iter_view_classes(patterns=None):
    patterns = patterns if patterns is not None else get_resolver().url_patterns
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from iter_view_classes(entry.url_patterns)
        elif isinstance(entry, URLPattern):
            cls = getattr(entry.callback, "cls", None)
            if cls is not None and issubclass(cls, APIView):
                yield cls


def exposed_model(view_cls):
    model = getattr(view_cls, "model", None)
    if model is None:
        serializer_class = getattr(view_cls, "serializer_class", None)
        meta = getattr(serializer_class, "Meta", None)
        model = getattr(meta, "model", None)
    return model


def owned_views():
    seen = set()
    for cls in iter_view_classes():
        if cls in seen:
            continue
        seen.add(cls)
        model = exposed_model(cls)
        if model is not None and issubclass(model, OwnedModel):
            yield cls


@pytest.mark.parametrize("view_cls", list(owned_views()), ids=lambda c: c.__name__)
def test_owned_views_use_scoping_mixin(view_cls):
    assert issubclass(view_cls, OwnedQuerySetMixin), f"{view_cls.__name__} lacks OwnedQuerySetMixin"
    assert getattr(view_cls, "model", None) is not None, f"{view_cls.__name__} must declare `model`"


def test_view_scan_finds_something():
    """Guard against the scan silently matching nothing (e.g. after a URL refactor)."""
    assert len(list(iter_view_classes())) >= 4
