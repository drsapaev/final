#!/usr/bin/env bash
set -euo pipefail

# --- Defaults ---
: "${HOST:=0.0.0.0}"
: "${PORT:=8000}"
: "${APP_MODULE:=app.main:app}"
: "${WORKERS:=1}"
: "${RELOAD:=0}"
# Keep the fallback aligned with backend config/env templates.
# /data remains available for explicit SQLite overrides, but it is no longer
# the silent default path for startup.
: "${DATABASE_URL:=sqlite:///./clinic.db}"
: "${ENSURE_ADMIN:=0}"

mkdir -p /data
export DATABASE_URL

echo "[entrypoint] Schema bootstrap is not part of implicit startup."
echo "[entrypoint] Expected flow: prepare schema explicitly (for example: alembic upgrade head), then start the app."

if [[ "${ENSURE_ADMIN}" == "1" ]]; then
  echo "[entrypoint] ENSURE_ADMIN=1 -> running explicit admin bootstrap..."
  python app/scripts/ensure_admin.py || echo "⚠️ Warning: Could not ensure admin user"
else
  echo "[entrypoint] ENSURE_ADMIN=${ENSURE_ADMIN} -> skipping admin bootstrap by default."
fi

echo "[entrypoint] Starting Uvicorn ${APP_MODULE} on ${HOST}:${PORT} (workers=${WORKERS}, reload=${RELOAD})"
exec uvicorn "${APP_MODULE}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  $( [[ "${RELOAD}" == "1" ]] && echo --reload )
