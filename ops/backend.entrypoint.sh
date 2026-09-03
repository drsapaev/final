#!/usr/bin/env bash
set -euo pipefail

# --- Defaults ---
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

# Blocking pre-deploy reconciliation (decision #13 doctor-linkage
# contract, Codex round-8 P2): refuse to serve while pre-existing data
# contains active Doctor rows without a live doctor-role owner (userless
# rows or legacy ghost owners). Break-glass: ALLOW_ACTIVE_USERLESS_DOCTORS=1
# explicitly skips the check (logged as a warning).
if [[ "${ALLOW_ACTIVE_USERLESS_DOCTORS:-0}" == "1" ]]; then
  echo "[entrypoint] WARNING: ALLOW_ACTIVE_USERLESS_DOCTORS=1 — skipping the doctor-linkage reconciliation check"
elif [[ "${RUN_ALEMBIC_ON_START}" == "1" ]]; then
  echo "[entrypoint] Checking doctor-linkage reconciliation (decision #13)..."
  # Codex round-9 P1: capture the script status WITHOUT `!` negation —
  # inside an `if ! cmd` branch $? is always 0, which masked the block
  # as a successful `exit 0`. Errexit is suspended around the probe so
  # the original status can be reported and re-raised verbatim.
  set +e
  python scripts/reconcile_userless_active_doctors.py
  rc=$?
  set -e
  if [[ "${rc}" -ne 0 ]]; then
    echo "[entrypoint] BLOCKED by doctor-linkage reconciliation (exit ${rc}). Resolve the inventory rows above or set ALLOW_ACTIVE_USERLESS_DOCTORS=1 explicitly." >&2
    exit "${rc}"
  fi
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
