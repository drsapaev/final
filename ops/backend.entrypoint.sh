#!/usr/bin/env bash
set -euo pipefail

# --- Defaults ---
: "${HOST:=0.0.0.0}"
: "${PORT:=8000}"
: "${APP_MODULE:=app.main:app}"
: "${WORKERS:=1}"
: "${RELOAD:=0}"
: "${DATABASE_URL:=sqlite:////data/app.db}"
: "${ENSURE_ADMIN:=1}"

mkdir -p /data
export DATABASE_URL

echo "[entrypoint] Running DB migrations..."
# retry once if first attempt fails (race on startup)
alembic upgrade head || (sleep 1 && alembic upgrade head)

if [[ "${ENSURE_ADMIN}" == "1" ]]; then
  echo "[entrypoint] Ensuring admin user..."
  python -m app.scripts.ensure_admin || true
fi

echo "[entrypoint] Starting Uvicorn ${APP_MODULE} on ${HOST}:${PORT} (workers=${WORKERS}, reload=${RELOAD})"
exec uvicorn "${APP_MODULE}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  $( [[ "${RELOAD}" == "1" ]] && echo --reload )