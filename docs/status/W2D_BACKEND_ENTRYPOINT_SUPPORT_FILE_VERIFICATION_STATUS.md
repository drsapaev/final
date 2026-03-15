# W2D Backend Entrypoint Support-File Verification Status

Status: completed

What changed:

- `ops/backend.entrypoint.sh` no longer forces `sqlite:////data/app.db` as the
  hidden startup default
- the entrypoint fallback now aligns with the backend env/config story via
  `sqlite:///./clinic.db`
- `ops/.env.example` now describes `/data/app.db` as an explicit SQLite
  override, not as the implied default path

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- supporting evidence was checked against:
  - `backend/app/core/config.py`
  - `backend/app/db/session.py`
  - `backend/.env.example`
  - `ops/.env.example`
  - `ops/README.md`

Result:

- the entrypoint no longer competes with the current backend template/config on
  the default SQLite path
- `create_all` and auto-admin remain explicitly unresolved startup semantics,
  not hidden follow-on edits for this slice
- the next honest step is a plan-gated review of those remaining startup tails
