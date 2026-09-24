"""Model fields with extra behaviour."""

from __future__ import annotations

import logging

from django.db import models

from apps.core import crypto

log = logging.getLogger("echo.core")


class EncryptedTextField(models.TextField):
    """Text stored encrypted at rest (see `apps.core.crypto`).

    Plain text in Python, Fernet token in the database. Empty strings stay empty, so
    `blank=True, default=""` means "not configured". Equality lookups on the ciphertext are
    meaningless (Fernet is randomised), so never filter on this field except for `""`.
    If the row was encrypted with a key that is no longer configured, the value reads back as
    `""` (and a warning is logged) instead of breaking every request that loads the model.
    """

    description = "Text encrypted at rest"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        return crypto.encrypt(str(value))

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return crypto.decrypt(value)
        except crypto.DecryptionError:
            log.warning("encrypted field %s could not be decrypted; treating as unset", self.name)
            return ""
