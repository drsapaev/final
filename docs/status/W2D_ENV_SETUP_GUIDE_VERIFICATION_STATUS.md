# W2D Env Setup Guide Verification Status

Status: completed

What changed:

- `backend/env_setup_guide.md` now points readers to `backend/.env.example`
  instead of teaching them to create a blank `.env` from scratch
- stale CORS examples were removed in favor of the current template-aligned
  minimum values
- dead `FCM_SETUP_GUIDE.md` references were removed
- the guide now clearly separates local/dev env setup from production/ops env
  docs

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- guide claims were checked against:
  - `backend/.env.example`
  - `ops/.env.example`
  - `backend/app/core/config.py`

Result:

- the backend env guide no longer competes with the live env template as a
  stale parallel source of truth
- the next low-risk env-docs target has shifted to `backend/.env.example`
