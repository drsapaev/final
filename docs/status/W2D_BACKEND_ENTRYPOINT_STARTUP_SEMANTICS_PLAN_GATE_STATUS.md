# W2D Backend Entrypoint Startup Semantics Plan Gate Status

Status: completed

What changed:

- the remaining `backend.entrypoint.sh` tails are now explicitly classified as
  startup semantics, not low-risk support-file cleanup
- neighboring ops/production docs now say more directly that:
  - the entrypoint runs `Base.metadata.create_all(...)` before startup
  - this is not a migration-first deployment guarantee
  - `ENSURE_ADMIN` defaults to `1` unless explicitly disabled

Validation:

- findings were checked against:
  - `ops/backend.entrypoint.sh`
  - `backend/app/scripts/ensure_admin.py`
  - `backend/alembic/env.py`
  - `ops/README.md`
  - `backend/SETUP_PRODUCTION.md`
  - `backend/PRODUCTION_SETUP_SUMMARY.md`
- `pytest tests/test_openapi_contract.py -q` -> `14 passed`

Result:

- hidden startup assumptions are now explicit
- runtime behavior is unchanged in this slice
- the next honest step is a human-reviewed policy decision on `create_all` and
  auto-admin bootstrap
