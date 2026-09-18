"""Structural guarantees: every business model is owned, scoped and fail-closed."""

import pytest
from django.apps import apps
from django.db import models

from apps.cards.models import Card, Category
from apps.core.context import NoOwnerContext, no_owner_context, owner_context
from apps.core.models import OwnedManager, OwnedModel

# Deliberate exceptions to "everything inherits OwnedModel".
ALLOWED_UNOWNED = {
    "accounts.User",
    "cards.Category",  # NULL owner = global category
    # future: "groups.StudyGroup", "groups.StudyGroupMembership"
}


def business_models():
    for model in apps.get_models():
        if not model._meta.app_label or model._meta.app_config.name.split(".")[0] != "apps":
            continue
        if model._meta.auto_created:  # implicit M2M through tables
            continue
        yield model


@pytest.mark.parametrize("model", list(business_models()), ids=lambda m: m._meta.label)
def test_every_business_model_is_owned_or_whitelisted(model):
    label = model._meta.label
    if label in ALLOWED_UNOWNED:
        return
    assert issubclass(model, OwnedModel), f"{label} must inherit OwnedModel"


@pytest.mark.parametrize(
    "model",
    [m for m in business_models() if issubclass(m, OwnedModel)],
    ids=lambda m: m._meta.label,
)
def test_owned_model_contract(model):
    assert isinstance(model._default_manager, OwnedManager), "default manager must be fail-closed"
    assert isinstance(model.all_users, models.Manager) and not isinstance(
        model.all_users, OwnedManager
    )
    user_field = model._meta.get_field("user")
    assert isinstance(user_field, models.ForeignKey)
    assert user_field.editable is False
    assert user_field.remote_field.on_delete is models.CASCADE
    for constraint in model._meta.constraints:
        if isinstance(constraint, models.UniqueConstraint):
            assert "user" in constraint.fields, (
                f"{model._meta.label}.{constraint.name} must include `user`"
            )


def test_category_constraints_are_scoped():
    names = {c.name: c for c in Category._meta.constraints}
    assert "uniq_global_category_slug" in names and names["uniq_global_category_slug"].condition
    assert names["uniq_personal_category_slug"].fields == ("owner", "slug")


@pytest.mark.django_db
def test_manager_fails_closed_without_context():
    with no_owner_context(), pytest.raises(NoOwnerContext):
        Card.objects.all()


@pytest.mark.django_db
def test_all_users_is_deliberate_global_access():
    with no_owner_context():
        assert Card.all_users.count() == 0


@pytest.mark.django_db
def test_manager_scopes_to_current_owner(user_a, user_b, make_card):
    card_a = make_card(user_a)
    card_b = make_card(user_b)
    with owner_context(user_a.pk):
        assert list(Card.objects.values_list("id", flat=True)) == [card_a.id]
        assert not Card.objects.filter(pk=card_b.pk).exists()
    with owner_context(user_b.pk):
        assert list(Card.objects.values_list("id", flat=True)) == [card_b.id]
    assert Card.all_users.count() == 2


@pytest.mark.django_db
def test_save_injects_owner_from_context(user_a, global_categories):
    with owner_context(user_a.pk):
        card = Card(
            category=global_categories["travel"],
            question_text="Where are you flying today?",
            cefr_level="A2",
            difficulty_rating=1100,
        )
        card.save()
    assert card.user_id == user_a.pk


@pytest.mark.django_db
def test_save_without_context_or_owner_fails(global_categories):
    with no_owner_context(), pytest.raises(NoOwnerContext):
        Card(
            category=global_categories["travel"],
            question_text="x",
            cefr_level="A2",
            difficulty_rating=1100,
        ).save()


@pytest.mark.django_db
def test_reverse_relations_are_scoped_too(user_a, user_b, make_card):
    """Related managers inherit the fail-closed manager."""
    card_a = make_card(user_a)
    with owner_context(user_b.pk):
        assert card_a.attempts.count() == 0
    with no_owner_context(), pytest.raises(NoOwnerContext):
        card_a.attempts.count()
