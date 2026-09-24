import base64
import hashlib

from .base import *  # noqa: F401,F403
from .base import ECHO_FIELD_ENCRYPTION_KEY, SECRET_KEY, env_bool

DEBUG = True
ALLOWED_HOSTS = ["*"]
INTERNAL_IPS = ["127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000"]
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
WHITENOISE_AUTOREFRESH = True

# Development only: derive the field-encryption key from SECRET_KEY when none is configured, so
# per-user API keys work out of the box. Production requires an explicit key (see prod.py).
if not ECHO_FIELD_ENCRYPTION_KEY:
    ECHO_FIELD_ENCRYPTION_KEY = base64.urlsafe_b64encode(
        hashlib.sha256(SECRET_KEY.encode()).digest()
    ).decode()
