#!/usr/bin/env bash
set -euo pipefail

# Expect PORT to be set via deployment environment (containers.json). No local default here to keep single source of truth.
if [ -z "${PORT:-}" ]; then
  echo "[startup] ERROR: PORT env var not set" >&2
  exit 1
fi

python manage.py migrate --noinput || {
  echo "[startup] migrate failed (exit $?)" >&2
  true
}

python manage.py ensure_superuser || {
  echo "[startup] ensure_superuser failed (exit $?)" >&2
  true
}

python manage.py create_beta_users || {
  echo "[startup] create_beta_users failed (exit $?)" >&2
  true
}

# Start Gunicorn (worker count/config comes from gunicorn.conf.py)
exec gunicorn wms.wsgi:application \
  --config /app/gunicorn.conf.py \
  --bind 0.0.0.0:"${PORT}"
