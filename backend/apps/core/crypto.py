"""Symmetric encryption for secrets stored in the database (per-user provider API keys).

Uses Fernet (AES-128-CBC + HMAC) with the key(s) in `ECHO_FIELD_ENCRYPTION_KEY`. Several keys may
be given separated by commas: the first one encrypts, all of them decrypt, which allows rotation
(re-save every row, then drop the old key). The key is deliberately separate from `SECRET_KEY`:
rotating the Django secret must never destroy stored API keys.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class DecryptionError(Exception):
    """The stored value was not produced with any of the configured keys."""


def derive_fernet_key(secret: str) -> str:
    """Deterministic Fernet key from an arbitrary secret (development convenience only)."""
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()).decode()


def _fernet() -> MultiFernet:
    raw = settings.ECHO_FIELD_ENCRYPTION_KEY
    keys = [k.strip() for k in (raw or "").split(",") if k.strip()]
    if not keys:
        raise ImproperlyConfigured(
            'ECHO_FIELD_ENCRYPTION_KEY is not set. Generate one with `python -c "from '
            'cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.'
        )
    try:
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(f"ECHO_FIELD_ENCRYPTION_KEY is not a valid Fernet key: {exc}")


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise DecryptionError("Value was not encrypted with the configured key(s).") from exc
