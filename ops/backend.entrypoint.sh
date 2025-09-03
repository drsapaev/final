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

echo "[entrypoint] Creating database tables..."
python -c "
import sys
sys.path.insert(0, '.')
from app.db.base import Base
from app.db.session import engine
try:
    Base.metadata.create_all(bind=engine)
    print('✅ Database tables created successfully')
except Exception as e:
    print(f'⚠️ Error creating tables: {e}')
    sys.exit(1)
"

if [[ "${ENSURE_ADMIN}" == "1" ]]; then
  echo "[entrypoint] Ensuring admin user..."
  python app/scripts/ensure_admin.py || true
fi

echo "[entrypoint] Starting Uvicorn ${APP_MODULE} on ${HOST}:${PORT} (workers=${WORKERS}, reload=${RELOAD})"
exec uvicorn "${APP_MODULE}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  $( [[ "${RELOAD}" == "1" ]] && echo --reload )