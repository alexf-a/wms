#!/usr/bin/env bash
set -euo pipefail

# Expect PORT to be set via deployment environment (containers.json). No local default here to keep single source of truth.
if [ -z "${PORT:-}" ]; then
  echo "[startup] ERROR: PORT env var not set" >&2
  exit 1
fi

# Run migrations (ok to fail if DB not reachable; container will restart)
python manage.py migrate --noinput || true

# Start Gunicorn (worker count/config comes from gunicorn.conf.py)
exec gunicorn wms.wsgi:application \
  --config /app/gunicorn.conf.py \
  --bind 0.0.0.0:"${PORT}"
