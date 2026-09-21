#!/bin/sh
# Usage: entrypoint.sh [web | worker | beat | <any command>]
#
# The role comes from the first argument or, when the container is started without arguments
# (the Coolify case: same image for every process, no start-command override in the Dockerfile
# build pack), from ECHO_PROCESS. Default: web.
set -e

ROLE="${1:-${ECHO_PROCESS:-web}}"

case "$ROLE" in
  web|worker|beat)
    # Read by /healthcheck.sh so the same HEALTHCHECK works for every role.
    echo "$ROLE" > /tmp/echo-role
    ;;
esac

case "$ROLE" in
  web)
    python manage.py migrate --noinput
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${WEB_CONCURRENCY:-2}" \
      --threads "${WEB_THREADS:-4}" \
      --timeout 120 \
      --access-logfile - --error-logfile -
    ;;
  worker)
    exec celery -A config worker -l info --concurrency "${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    exec celery -A config beat -l info
    ;;
  *)
    exec "$@"
    ;;
esac
