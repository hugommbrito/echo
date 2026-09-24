"""Base settings shared by every environment. Tunable product parameters live under ECHO_*."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from botocore.config import Config as BotoConfig
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_DIR = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    return int(raw) if raw not in (None, "") else default


def database_from_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "localhost",
        "PORT": str(parsed.port or 5432),
        "ATOMIC_REQUESTS": True,
        "OPTIONS": {"pool": True, **({"sslmode": query["sslmode"]} if "sslmode" in query else {})},
    }


SECRET_KEY = env("SECRET_KEY", "dev-insecure-secret-key-change-me")
DEBUG = False
ALLOWED_HOSTS: list[str] = [h for h in env("ALLOWED_HOSTS", "").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "storages",
    "apps.core",
    "apps.accounts",
    "apps.cards",
    "apps.scheduling",
    "apps.leveling",
    "apps.practice",
    "apps.ai",
    "apps.stats",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.OwnerContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": database_from_url(
        env("DATABASE_URL", "postgres://echo:echo@localhost:5432/echo")  # type: ignore[arg-type]
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static files (Django admin + built SPA served by WhiteNoise on the same domain) ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_DIST = Path(env("FRONTEND_DIST", str(REPO_DIR / "frontend" / "dist")))
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.exists() else None
WHITENOISE_INDEX_FILE = True

# --- Media / audio storage ---
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
AUDIO_STORAGE_BACKEND = env("ECHO_AUDIO_STORAGE", "filesystem")  # filesystem | s3

# botocore >= 1.36 adds a CRC32 checksum to every upload on its own and, to do so, streams the
# body as `Content-Encoding: aws-chunked`. Oracle Object Storage rejects that with
# `NotImplemented: AWS chunked encoding not supported`, so every PutObject fails. `when_required`
# keeps checksums only where the API mandates them and sends a plain Content-Length body.
# This config replaces the one django-storages would build, so it also carries the addressing
# style and the signature version (the `addressing_style`/`signature_version` options are only
# read when `client_config` is unset).
S3_CLIENT_CONFIG = BotoConfig(
    s3={"addressing_style": "path"},
    signature_version="s3v4",
    request_checksum_calculation="when_required",
    response_checksum_validation="when_required",
)

if AUDIO_STORAGE_BACKEND == "s3":
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": env("S3_BUCKET_NAME"),
                "endpoint_url": env("S3_ENDPOINT_URL"),
                "access_key": env("S3_ACCESS_KEY_ID"),
                "secret_key": env("S3_SECRET_ACCESS_KEY"),
                "region_name": env("S3_REGION", "us-ashburn-1"),
                "default_acl": None,
                "querystring_auth": True,
                "querystring_expire": env_int("S3_SIGNED_URL_SECONDS", 900),
                "file_overwrite": False,
                "client_config": S3_CLIENT_CONFIG,
            },
        },
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

# --- Sessions / CSRF (SPA on the same origin) ---
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [o for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Echo API",
    "DESCRIPTION": (
        "Speaking practice (English and French) with spaced repetition and an adaptive level "
        "per language."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "SessionStatusEnum": "apps.practice.models.SessionStatus",
        "AttemptStatusEnum": "apps.practice.models.AttemptStatus",
        "CardStatusEnum": "apps.cards.models.CardStatus",
        "LanguageCodeEnum": "apps.core.languages.LanguageCode",
        "PlanStatusEnum": "apps.practice.models.PlanStatus",
        "QuestionModeEnum": "apps.accounts.models.QuestionMode",
    },
}

# --- Celery ---
REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 60 * 5
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 4
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True

# --- External providers (global keys; users may bring their own, see apps.ai.routing) ---
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
OPENAI_API_KEY = env("OPENAI_API_KEY")
# Fernet key(s) for secrets stored in the database (per-user API keys). Comma-separated for
# rotation: the first encrypts, all decrypt. Required in production (see prod.py).
ECHO_FIELD_ENCRYPTION_KEY = env("ECHO_FIELD_ENCRYPTION_KEY")

# =====================================================================================
# ECHO_* — product parameters (see docs/PLAN.md §12.2). Change here, never in code.
# =====================================================================================
ECHO_AI_PROVIDER = env("ECHO_AI_PROVIDER", "live")  # live | fake
# Practised languages live in apps/core/languages.py; these pick defaults.
ECHO_DEFAULT_LANGUAGE = "en"
ECHO_SELF_PLACEMENT_LEVELS = ["A1", "A2", "B1"]
ECHO_SELF_PLACEMENT_DEFAULT_LEVEL = "A1"
ECHO_PROMPT_VERSION = "v3"
ECHO_EVALUATION_MODEL = env("ECHO_EVALUATION_MODEL", "claude-opus-5")
ECHO_EVALUATION_EFFORT = env("ECHO_EVALUATION_EFFORT", "medium")
ECHO_GENERATION_MODEL = env("ECHO_GENERATION_MODEL", "claude-sonnet-5")
ECHO_GENERATION_EFFORT = env("ECHO_GENERATION_EFFORT", "medium")
ECHO_IMPROVED_ANSWER_MODEL = env("ECHO_IMPROVED_ANSWER_MODEL", "claude-sonnet-5")
ECHO_IMPROVED_ANSWER_EFFORT = env("ECHO_IMPROVED_ANSWER_EFFORT", "low")
ECHO_TRANSCRIPTION_MODEL = env("ECHO_TRANSCRIPTION_MODEL", "whisper-1")
ECHO_IMPROVED_ANSWER_TIMEOUT_SECONDS = 30
# Text tasks per LLM provider. Anthropic is the default; OpenAI serves users who only bring an
# OpenAI key (and everyone when no Anthropic key exists at all). Efforts above are shared: they
# are valid `reasoning.effort` values on OpenAI too.
ECHO_MODELS = {
    "anthropic": {
        "evaluation": ECHO_EVALUATION_MODEL,
        "generation": ECHO_GENERATION_MODEL,
        "improved_answer": ECHO_IMPROVED_ANSWER_MODEL,
    },
    "openai": {
        "evaluation": env("ECHO_OPENAI_EVALUATION_MODEL", "gpt-6-astra"),
        "generation": env("ECHO_OPENAI_GENERATION_MODEL", "gpt-6-sol"),
        "improved_answer": env("ECHO_OPENAI_IMPROVED_ANSWER_MODEL", "gpt-6-sol"),
    },
}

# Text-to-speech (spoken question). One voice per practised language; `instructions` steer
# accent and pace and are only sent to models that accept them (gpt-4o-mini-tts).
ECHO_TTS_MODEL = env("ECHO_TTS_MODEL", "gpt-4o-mini-tts")
ECHO_TTS_FORMAT = env("ECHO_TTS_FORMAT", "mp3")
ECHO_TTS_TIMEOUT_SECONDS = env_int("ECHO_TTS_TIMEOUT_SECONDS", 30)
ECHO_TTS_VOICES = {
    "en": env("ECHO_TTS_VOICE_EN", "marin"),
    "fr": env("ECHO_TTS_VOICE_FR", "cedar"),
}
ECHO_TTS_INSTRUCTIONS = {
    "en": env(
        "ECHO_TTS_INSTRUCTIONS_EN",
        "Speak clearly and naturally at a calm, unhurried pace, like a friendly person in Canada "
        "asking someone one question. Neutral North American accent.",
    ),
    "fr": env(
        "ECHO_TTS_INSTRUCTIONS_FR",
        "Speak natural Québec French clearly at a calm, unhurried pace, like a friendly person in "
        "Montréal asking someone one question. Standard Québec pronunciation, not European French.",
    ),
}

# Thinking time (question shown -> record pressed), compared with the learner's own recent
# history per language. Never part of the composite score, SM-2 or the rating.
ECHO_THINKING_BASELINE_WINDOW = 20  # attempts used for the personal median
ECHO_THINKING_BASELINE_MIN_SAMPLES = 5  # below this, the default baseline applies
ECHO_THINKING_DEFAULT_BASELINE_SECONDS = 6
ECHO_THINKING_MAX_SECONDS = 900  # values above are clamped (a tab left open)
ECHO_THINKING_YELLOW_RATIO = 1.5  # green <= 1.0x baseline, yellow <= 1.5x, red above; no floor

# Scores
ECHO_COMPOSITE_WEIGHTS = {"structure": 0.40, "grammar": 0.35, "fluency": 0.25}
ECHO_STRUCTURE_FAIL_THRESHOLD = 2  # structure_score <= 2 => quality capped at 2
ECHO_MIN_WORDS_FOR_EVALUATION = 5

# SM-2 scheduler
ECHO_SM2_MAX_INTERVAL_DAYS = 180
ECHO_SM2_MATURE_THRESHOLD_DAYS = 21
ECHO_SM2_MIN_EASE = 1.30
ECHO_SM2_INITIAL_EASE = 2.50
ECHO_SM2_VERSION = "sm2-v1"

# Adaptive level (ELO-style)
ECHO_LEVEL_INITIAL_RATING = 1150
ECHO_LEVEL_RATING_MIN = 600
ECHO_LEVEL_RATING_MAX = 2200
ECHO_LEVEL_BANDS = [
    # label, min rating (inclusive), max rating (inclusive), center rating for a typical question
    {"label": "A1", "min": 0, "max": 999, "center": 900},
    {"label": "A2", "min": 1000, "max": 1199, "center": 1100},
    {"label": "B1", "min": 1200, "max": 1399, "center": 1300},
    {"label": "B2", "min": 1400, "max": 1599, "center": 1500},
    {"label": "C1", "min": 1600, "max": 1799, "center": 1700},
    {"label": "C2", "min": 1800, "max": 10_000, "center": 1900},
]
ECHO_LEVEL_DIFFICULTY_OFFSETS = {"easier": -60, "typical": 0, "harder": 60}
ECHO_LEVEL_K_SCHEDULE = [
    # (counted attempts up to and including, K)
    (20, 40),
    (100, 24),
    (None, 16),
]
ECHO_LEVEL_VERSION = "elo-v1"
ECHO_PROBE_RATIO = 0.20
ECHO_PROBE_MIN_GENERATED_FOR_PROBE = 3

# Generation / sessions
ECHO_GENERATION_RECENT_QUESTIONS = 80
ECHO_MAX_NEW_CARDS_PER_DAY = 20

# Audio
ECHO_AUDIO_MIN_SECONDS = 3.0
ECHO_AUDIO_MAX_SECONDS = 300.0
ECHO_AUDIO_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ECHO_FFPROBE_BIN = env("ECHO_FFPROBE_BIN", "ffprobe")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"echo": {"level": env("LOG_LEVEL", "INFO")}},
}
