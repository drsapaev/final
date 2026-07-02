#!/usr/bin/env bash
set -euo pipefail

: "${HOST:=0.0.0.0}"
: "${PORT:=18000}"
: "${APP_MODULE:=app.main:app}"
: "${WORKERS:=1}"
: "${RELOAD:=0}"
: "${DATABASE_URL:?DATABASE_URL must be set to a PostgreSQL connection string}"
: "${ENSURE_ADMIN:=1}"
: "${RUN_ALEMBIC_ON_START:=1}"

mkdir -p /data
export DATABASE_URL

case "${DATABASE_URL,,}" in
  sqlite:*)
    echo "[entrypoint] Refusing SQLite DATABASE_URL. PostgreSQL + Alembic are the schema source of truth." >&2
    exit 1
    ;;
esac

if [[ "${RUN_ALEMBIC_ON_START}" == "1" ]]; then
  echo "[entrypoint] Running alembic upgrade head..."
  alembic upgrade head
else
  echo "[entrypoint] Alembic migration skipped because RUN_ALEMBIC_ON_START=${RUN_ALEMBIC_ON_START}"
fi

if [[ "${ENSURE_ADMIN}" == "1" ]]; then
  echo "[entrypoint] Ensuring admin user..."
  python app/scripts/ensure_admin.py || echo "[entrypoint] Warning: Could not ensure admin user"
fi

echo "[entrypoint] Starting Uvicorn ${APP_MODULE} on ${HOST}:${PORT} (workers=${WORKERS}, reload=${RELOAD})"
exec uvicorn "${APP_MODULE}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  $( [[ "${RELOAD}" == "1" ]] && echo --reload )
