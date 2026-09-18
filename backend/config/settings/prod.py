from .base import *  # noqa: F401,F403
from .base import env, env_bool

DEBUG = False
SECRET_KEY = env("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in production")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)  # Traefik already redirects
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Vite emits hashed asset names like assets/index-BxYz1234.js -> cache them as immutable.
WHITENOISE_IMMUTABLE_FILE_TEST = lambda path, url: bool(  # noqa: E731
    __import__("re").search(r"/assets/.+-[0-9A-Za-z_-]{8,}\.[a-z0-9]+$", url)
)
