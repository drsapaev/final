# W2D Setup Production Verification Plan

Scope:

- verify `backend/SETUP_PRODUCTION.md` against current backend config,
  published endpoints, helper scripts, and deployment files
- verify the companion `backend/PRODUCTION_SETUP_SUMMARY.md` in the same
  bounded docs-only slice
- preserve useful setup commands while downgrading stale production claims

Evidence targets:

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

Expected outcome:

- setup docs stop reading like drop-in production approval
- compose/env drift is called out explicitly instead of silently preserved
- monitoring and readiness helpers are reframed as optional/manual where needed
- the next honest production-docs target shifts to
  `backend/PRODUCTION_READINESS_CHECKLIST.md`
