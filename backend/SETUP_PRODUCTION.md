# Production Setup Guide

Reviewed For Drift: 2026-03-14
Status: curated setup runbook with current caveats

## How to use this file

This file is not a current go-live approval memo.

Use it as a bounded setup/runbook reference, then confirm current execution
status in:

- `C:/final/docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
- `C:/final/docs/status/OPENHANDS_TASK_BACKLOG.md`
- `C:/final/docs/OPERATOR_STARTUP_COMMANDS.md`

Current code-backed verification baseline:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- `pytest -q` -> `850 passed, 3 skipped`

## Verified Repo-Backed Assets

These setup helpers currently exist in the repo:

- `backend/.env.example`
- `backend/generate_secret_key.py`
- `backend/load_test.py`
- `backend/requirements-monitoring.txt`
- `ops/docker-compose.yml`
- `ops/backend.entrypoint.sh`

These runtime endpoints are currently published in `backend/openapi.json`:

- `GET /api/v1/health`
- `GET /api/v1/status`
- `POST /api/v1/system/backup/create`
- `GET /api/v1/system/backup/list`

## Current Caveats

- `ops/docker-compose.yml` expects `backend/.env.production`, but that file is
  not committed in the repo.
- The current compose defaults are not production-safe as written:
  - it sets `AUTH_SECRET`, while the active app config validates `SECRET_KEY`
  - it defaults `ENV=dev`
  - it defaults `CORS_ALLOW_ALL=1`, while `app.main` refuses permissive CORS
    in production
- `ops/backend.entrypoint.sh` no longer performs schema bootstrap on startup;
  schema preparation is now an explicit operator step
- `ops/backend.entrypoint.sh` now defaults `ENSURE_ADMIN=0`, so admin
  bootstrap only happens when operators opt in explicitly
- `gunicorn` is not present in `backend/requirements.txt`; the repo-backed
  server runtime is `uvicorn`.
- `backend/monitoring_config.py` and
  `backend/requirements-monitoring.txt` exist as optional helper tooling, but
  they are not auto-wired from `app/main.py`.
- `backend/test_production_readiness.py` still exists, but it is a legacy
  spot-check script, not the current canonical pass/fail gate for the repo.

## Step 1: Environment Baseline

### 1.1 Copy the env template

```bash
cd backend
cp .env.example .env
```

### 1.2 Generate `SECRET_KEY`

```bash
python generate_secret_key.py
```

Copy the generated value into `.env`:

```env
SECRET_KEY=your-generated-secret-key-here
```

### 1.3 Set the minimum required values

At minimum, review and set:

```env
# Critical
SECRET_KEY=your-secret-key-here
ENV=production

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/clinic

# CORS
BACKEND_CORS_ORIGINS=https://your-domain.com
FRONTEND_URL=https://your-domain.com

# FCM (optional)
FCM_ENABLED=true
FCM_SERVER_KEY=your-fcm-server-key
FCM_PROJECT_ID=your-fcm-project-id

# Backup (recommended)
AUTO_BACKUP_ENABLED=true
BACKUP_HOUR=2
BACKUP_MINUTE=0
```

Notes:

- the current `.env.example` still uses legacy `CORS_ORIGINS`; the active app
  config accepts both `CORS_ORIGINS` and `BACKEND_CORS_ORIGINS`
- in production, the app validates `SECRET_KEY` and rejects permissive CORS
  settings
- PostgreSQL is the production-oriented database path; production config warns
  against SQLite

## Step 2: Database Migrations

### 2.1 Run migrations

```bash
cd backend
alembic upgrade head
```

### 2.2 Verify migration status

```bash
alembic current
```

## Step 3: Optional Admin Bootstrap

Run this only if you intentionally want the helper to create or normalize an
admin user:

```bash
cd backend
python app/scripts/ensure_admin.py
```

Important caveat:

- this script can create a user, promote a user to `Admin`, reactivate a user,
  and optionally reset the password if `ADMIN_RESET_PASSWORD=1`
- mutation of an existing matched user now requires explicit
  `ADMIN_ALLOW_UPDATE=1`
- treat it as an operator command, not as normal app startup

## Step 4: Optional Observability Helpers

If you want the optional helper stack that exists in this repo:

```bash
pip install -r requirements-monitoring.txt
```

Optional env values for that helper layer:

```env
SENTRY_DSN=your-sentry-dsn
SENTRY_TRACES_SAMPLE_RATE=0.1
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
```

Important caveat:

- this helper layer is not auto-started by `app/main.py`
- treat it as manual/extra wiring, not as a default production startup path

## Step 5: Load Testing Helper

### 5.1 Run load tests

```bash
# Basic test
python load_test.py

# Custom test
python load_test.py --users 50 --requests 20 --url http://your-api-url

# Test a specific endpoint
python load_test.py --endpoint /api/v1/patients/ --users 10 --requests 100
```

### 5.2 Treat thresholds as operator targets, not enforced gates

The helper remains useful for spot checks, but these are operator targets,
not current CI-enforced gates:

- Success rate: `> 95%`
- Average response time: `< 500ms`
- P95 response time: `< 2000ms`
- Error rate: `< 5%`

## Step 6: Start the Server

### 6.1 Repo-backed local server path

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6.2 Gunicorn is optional and requires separate installation

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Use that only if you install `gunicorn` separately. It is not part of the
repo's default Python dependency set.

### 6.3 Docker compose exists, but review env defaults first

```bash
docker compose -f ops/docker-compose.yml run --rm backend alembic upgrade head
# optional explicit admin bootstrap:
# docker compose -f ops/docker-compose.yml run --rm backend python app/scripts/ensure_admin.py
# if you intentionally want to mutate an existing matched user:
# docker compose -f ops/docker-compose.yml run --rm -e ADMIN_ALLOW_UPDATE=1 backend python app/scripts/ensure_admin.py
docker compose -f ops/docker-compose.yml up --build -d
```

Before treating compose as production-ready, review:

- missing committed `backend/.env.production`
- `AUTH_SECRET` versus `SECRET_KEY`
- `ENV=dev` default
- `CORS_ALLOW_ALL=1` default
- explicit migration step before startup
- explicit `ENSURE_ADMIN=1` only when admin bootstrap is intended

## Step 7: Verify the Live App

### 7.1 Health checks

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/status
```

### 7.2 Canonical repo verification

```bash
pytest tests/test_openapi_contract.py -q
pytest -q
```

### 7.3 Legacy readiness script (optional spot check only)

```bash
python test_production_readiness.py
```

Treat that script as a historical helper, not as the authoritative "all clear"
signal for the repo.

## Step 8: Backup Verification

### 8.1 Manual backup smoke test

```bash
curl -X POST http://localhost:8000/api/v1/system/backup/create \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"

curl http://localhost:8000/api/v1/system/backup/list \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 8.2 Automated backup log check

```bash
tail -f logs/app.log | grep backup
```

## Security Review Checklist

- [ ] `SECRET_KEY` is set to a unique secure value
- [ ] `ENV=production`
- [ ] CORS origins are strict and intentional
- [ ] Database credentials are secure
- [ ] `FRONTEND_URL` is reviewed for production usage
- [ ] FCM keys are configured only if needed
- [ ] Payment provider keys are configured securely if enabled
- [ ] Telegram bot token is configured securely if enabled
- [ ] Backup flow is tested
- [ ] Monitoring/logging expectations are reviewed explicitly
- [ ] Rate limiting is enabled as intended
- [ ] 2FA flows are validated if required for the deployment

## Troubleshooting

### Migration issues

```bash
alembic current
alembic history
alembic downgrade -1
```

### Load test issues

1. Check server logs.
2. Verify database connectivity.
3. Check CPU and memory usage.
4. Review endpoint-specific error output from `load_test.py`.

### Monitoring helper issues

1. Verify `pip install -r requirements-monitoring.txt`.
2. Check `SENTRY_DSN`, `PROMETHEUS_ENABLED`, and `PROMETHEUS_PORT`.
3. Confirm you actually wired the helper into your startup flow.

## Next Recommended Doc

For the next neighboring production-docs audit, use:

- `backend/PRODUCTION_SETUP_SUMMARY.md`
