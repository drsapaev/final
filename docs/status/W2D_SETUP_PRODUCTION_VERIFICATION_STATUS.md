# W2D Setup Production Verification Status

Status: completed

What changed:

- `backend/SETUP_PRODUCTION.md` now reads as a curated setup runbook with
  current caveats instead of a current deployment approval path
- `backend/PRODUCTION_SETUP_SUMMARY.md` now reads as a shorter orientation page
  instead of a completion-style production setup announcement
- compose/env drift is now called out explicitly:
  - missing committed `backend/.env.production`
  - `AUTH_SECRET` versus `SECRET_KEY`
  - `ENV=dev` and `CORS_ALLOW_ALL=1` defaults
- monitoring helpers, gunicorn, and `test_production_readiness.py` are now
  framed as optional/manual or legacy where that is what the repo evidence
  supports

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- setup claims were checked against:
  - `backend/app/main.py`
  - `backend/app/core/config.py`
  - `backend/openapi.json`
  - `backend/.env.example`
  - `backend/generate_secret_key.py`
  - `backend/load_test.py`
  - `backend/requirements-monitoring.txt`
  - `backend/monitoring_config.py`
  - `backend/test_production_readiness.py`
  - `ops/docker-compose.yml`
  - `ops/backend.entrypoint.sh`
  - `backend/requirements.txt`

Result:

- the production setup docs are now more honest about what the current repo
  proves versus what still needs operator review
- the next low-risk production-docs target has shifted to
  `backend/PRODUCTION_READINESS_CHECKLIST.md`
