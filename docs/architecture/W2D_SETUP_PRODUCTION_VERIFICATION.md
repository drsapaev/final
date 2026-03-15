# W2D Setup Production Verification

## Summary

This was a bounded docs-vs-code audit for:

- `backend/SETUP_PRODUCTION.md`
- `backend/PRODUCTION_SETUP_SUMMARY.md`

The goal was not to invent a new deployment platform. The goal was to stop the
neighboring production setup docs from over-claiming "ready to deploy"
behavior where the current repo only proves partial setup helpers.

## Findings

### The setup docs still read too much like a drop-in production runbook

- both files still implied a straightforward "complete the steps and deploy"
  story
- but the current repo includes important deployment caveats:
  - `ops/docker-compose.yml` expects `backend/.env.production`, which is not
    committed
  - compose still uses `AUTH_SECRET`, while active app config validates
    `SECRET_KEY`
  - compose defaults `ENV=dev` and `CORS_ALLOW_ALL=1`, which conflicts with
    production-safe startup rules in `app/main.py`

### Monitoring and readiness helpers are optional, not startup-default

- `backend/requirements-monitoring.txt` and `backend/monitoring_config.py`
  still exist and remain useful
- but `monitoring_config.py` is not auto-imported by `backend/app/main.py`
- the honest docs move was to keep those helpers visible while downgrading
  them from default startup expectations to optional/manual wiring

### Gunicorn and the legacy readiness script needed clearer framing

- `uvicorn` is present in repo dependencies
- `gunicorn` is not present in `backend/requirements.txt`
- `backend/test_production_readiness.py` still exists, but it is a legacy
  spot-check harness rather than the canonical repo-wide verification gate
- the setup docs now distinguish repo-backed verification from optional legacy
  helpers

## What changed

- reframed `backend/SETUP_PRODUCTION.md` as a curated setup runbook with
  current caveats
- preserved useful setup commands for env, migrations, health checks, load
  tests, and backup checks
- downgraded the compose, monitoring, gunicorn, and readiness-script claims to
  match current repo evidence
- reframed `backend/PRODUCTION_SETUP_SUMMARY.md` from a completion-style
  announcement into a shorter orientation page with current caveats and a
  safer quick-start sequence

## Evidence used

- `backend/SETUP_PRODUCTION.md`
- `backend/PRODUCTION_SETUP_SUMMARY.md`
- `backend/.env.example`
- `backend/generate_secret_key.py`
- `backend/load_test.py`
- `backend/requirements-monitoring.txt`
- `backend/monitoring_config.py`
- `backend/test_production_readiness.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/openapi.json`
- `ops/docker-compose.yml`
- `ops/backend.entrypoint.sh`
- `backend/requirements.txt`

## Verification

- `pytest tests/test_openapi_contract.py -q`

## Recommended next step

Continue the neighboring production-docs cleanup with:

- `backend/PRODUCTION_READINESS_CHECKLIST.md`

Why:

- it is the next obvious production-facing doc that still reads like a current
  live readiness verdict
- it likely contains more point-in-time validation counts and "ready" language
  that should be checked against the current repo before preserving
