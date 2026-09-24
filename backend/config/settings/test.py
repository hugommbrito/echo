"""Test settings: SQLite by default (fast, no services); Postgres when DATABASE_URL is set."""

import tempfile
from pathlib import Path

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, database_from_url, env

DEBUG = False
SECRET_KEY = "test-secret-key"
ALLOWED_HOSTS = ["*"]

_test_db_url = env("TEST_DATABASE_URL") or env("DATABASE_URL")
if _test_db_url and env("ECHO_TEST_USE_POSTGRES", "0") == "1":
    DATABASES = {"default": database_from_url(_test_db_url)}
    DATABASES["default"]["OPTIONS"] = {}  # no pooling in tests
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test.sqlite3",
            "ATOMIC_REQUESTS": True,
        }
    }

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="echo-test-media-"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
WHITENOISE_ROOT = None
WHITENOISE_AUTOREFRESH = True

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

ECHO_AI_PROVIDER = "fake"
ANTHROPIC_API_KEY = "test"
OPENAI_API_KEY = "test"
# Fixed Fernet key so encrypted fields are deterministic to set up in tests.
ECHO_FIELD_ENCRYPTION_KEY = "5OMonGvQZ_NfmWnFtJqPNvwdfQ2wmPozpPlFz_ZsA5o="
