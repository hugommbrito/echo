#!/bin/sh
# Docker HEALTHCHECK shared by every role of the image (see entrypoint.sh).
#   web    -> HTTP 200 from /healthz/ (also checks the database connection)
#   worker -> the Celery worker of this container answers a ping through the broker
#   beat   -> nothing to probe; report healthy
#   other  -> report healthy (one-off commands)
ROLE="$(cat /tmp/echo-role 2>/dev/null || echo web)"

case "$ROLE" in
  web)
    # Django rejects Host headers outside ALLOWED_HOSTS, so send the first configured host
    # (falls back to localhost for empty or wildcard entries such as ".example.com").
    HOST="${ALLOWED_HOSTS%%,*}"
    case "$HOST" in ""|.*|\**) HOST=localhost ;; esac
    exec curl -fsS -H "Host: $HOST" "http://localhost:8000/healthz/"
    ;;
  worker)
    exec celery -A config inspect ping -d "celery@$(hostname)" --timeout 10
    ;;
  *)
    exit 0
    ;;
esac
