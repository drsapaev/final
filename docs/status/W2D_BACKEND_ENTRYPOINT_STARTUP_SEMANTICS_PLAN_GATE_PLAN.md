# W2D Backend Entrypoint Startup Semantics Plan Gate Plan

Scope:

- review the remaining behavior-bearing startup semantics in
  `ops/backend.entrypoint.sh`
- do not silently change startup behavior in this slice
- prefer explicit decision framing over opportunistic runtime edits

Primary review targets:

- `Base.metadata.create_all(...)`
- `ENSURE_ADMIN`
- `backend/app/scripts/ensure_admin.py`

Supporting evidence:

- `backend/alembic/env.py`
- `backend/SETUP_PRODUCTION.md`
- `backend/PRODUCTION_SETUP_SUMMARY.md`
- `ops/README.md`

Expected outcome:

- startup semantics classified as review-required, not low-risk cleanup
- neighboring docs made explicit about current behavior
- next step shifted to a human-reviewed policy decision instead of another
  silent support-file patch
