"""Per-user provider keys are entered by the admin only, stored encrypted and never echoed."""

import pytest

from apps.accounts.admin import UserChangeForm
from apps.accounts.models import key_hint

pytestmark = pytest.mark.django_db


def _form(user, **extra):
    data = {
        "email": user.email,
        "full_name": user.full_name,
        "timezone": user.timezone,
        "feedback_language": user.feedback_language,
        "question_mode": user.question_mode,
        "show_thinking_timer": "on" if user.show_thinking_timer else "",
        "is_active": "on",
        "date_joined": user.date_joined.strftime("%Y-%m-%d %H:%M:%S"),
        **extra,
    }
    return UserChangeForm(data=data, instance=user)


def test_admin_form_sets_replaces_and_clears_keys(user_a):
    form = _form(user_a, new_anthropic_api_key="sk-ant-api03-first1234")
    assert form.is_valid(), form.errors
    user = form.save()
    user.refresh_from_db()
    assert user.anthropic_api_key == "sk-ant-api03-first1234"
    assert user.anthropic_api_key_updated_at is not None
    assert user.openai_api_key == "" and user.openai_api_key_updated_at is None

    # blank keeps the current key; a new value replaces it
    form = _form(user, new_openai_api_key="sk-proj-second5678")
    assert form.is_valid(), form.errors
    user = form.save()
    user.refresh_from_db()
    assert user.anthropic_api_key == "sk-ant-api03-first1234"
    assert user.openai_api_key == "sk-proj-second5678"

    form = _form(user, clear_anthropic_api_key="on", new_anthropic_api_key="sk-ant-ignored")
    assert form.is_valid(), form.errors
    user = form.save()
    user.refresh_from_db()
    assert user.anthropic_api_key == "" and user.anthropic_api_key_updated_at is None
    assert user.openai_api_key == "sk-proj-second5678"


def test_admin_form_rejects_implausible_keys(user_a):
    form = _form(user_a, new_anthropic_api_key="sk-proj-not-anthropic")
    assert not form.is_valid() and "new_anthropic_api_key" in form.errors
    form = _form(user_a, new_openai_api_key="has spaces sk-")
    assert not form.is_valid() and "new_openai_api_key" in form.errors


def test_admin_form_never_renders_the_stored_keys(user_a):
    user_a.anthropic_api_key = "sk-ant-api03-hidden9999"
    user_a.save()
    html = UserChangeForm(instance=user_a).as_p()
    assert "hidden9999" not in html
    assert "anthropic_api_key" not in [
        name
        for name in UserChangeForm(instance=user_a).fields
        if name in {"anthropic_api_key", "openai_api_key"}
    ]


def test_key_hint():
    assert key_hint("sk-ant-api03-abcd1234") == "…1234"
    assert key_hint("") is None and key_hint(None) is None
