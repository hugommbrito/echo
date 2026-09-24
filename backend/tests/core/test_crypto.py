"""Fernet encryption for per-user API keys (`apps.core.crypto`, `EncryptedTextField`)."""

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from apps.core import crypto


def test_roundtrip_and_ciphertext_is_randomised():
    token = crypto.encrypt("sk-ant-api03-secret")
    assert token != "sk-ant-api03-secret" and token.startswith("gAAAA")
    assert crypto.decrypt(token) == "sk-ant-api03-secret"
    assert crypto.encrypt("x") != crypto.encrypt("x")


def test_wrong_key_is_a_clear_error(settings):
    token = crypto.encrypt("secret")
    settings.ECHO_FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(token)


def test_rotation_accepts_old_keys_and_encrypts_with_the_first(settings):
    old = settings.ECHO_FIELD_ENCRYPTION_KEY
    token = crypto.encrypt("secret")
    new = Fernet.generate_key().decode()
    settings.ECHO_FIELD_ENCRYPTION_KEY = f"{new}, {old}"
    assert crypto.decrypt(token) == "secret"
    fresh = crypto.encrypt("again")
    settings.ECHO_FIELD_ENCRYPTION_KEY = new
    assert crypto.decrypt(fresh) == "again"


def test_missing_or_invalid_key_is_a_configuration_error(settings):
    settings.ECHO_FIELD_ENCRYPTION_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        crypto.encrypt("x")
    settings.ECHO_FIELD_ENCRYPTION_KEY = "not-a-fernet-key"
    with pytest.raises(ImproperlyConfigured):
        crypto.encrypt("x")


def test_derived_key_is_a_valid_fernet_key():
    Fernet(crypto.derive_fernet_key("dev-insecure-secret-key").encode())


@pytest.mark.django_db
def test_encrypted_field_stores_ciphertext_and_reads_plaintext(user_a, settings):
    from django.db.models import TextField
    from django.db.models.expressions import RawSQL

    from apps.accounts.models import User

    user_a.anthropic_api_key = "sk-ant-api03-fieldsecret"
    user_a.save()
    stored = (
        User.objects.filter(pk=user_a.pk)
        .annotate(raw=RawSQL("anthropic_api_key", (), output_field=TextField()))
        .values_list("raw", flat=True)
        .get()
    )
    assert stored and "fieldsecret" not in stored
    user_a.refresh_from_db()
    assert user_a.anthropic_api_key == "sk-ant-api03-fieldsecret"
    assert user_a.openai_api_key == ""

    # a row encrypted with a key that is no longer configured reads back as "unset"
    settings.ECHO_FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    user_a.refresh_from_db()
    assert user_a.anthropic_api_key == ""
