#!/bin/sh
# Usage: entrypoint.sh web | worker | beat | <any command>
set -e

case "$1" in
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
