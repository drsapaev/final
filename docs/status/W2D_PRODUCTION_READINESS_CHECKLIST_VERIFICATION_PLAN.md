# W2D Production Readiness Checklist Verification Plan

Scope:

- verify `backend/PRODUCTION_READINESS_CHECKLIST.md` against current FK/schema
  scripts and runtime/config evidence
- keep the slice docs-only
- preserve useful helper commands while downgrading stale whole-system
  production claims

Evidence targets:

- `backend/validate_production_readiness.py`
- `backend/verify_fk_enforcement.py`
- `backend/validate_fk_policies.py`
- `backend/cleanup_orphaned_records.py`
- `backend/app/scripts/audit_foreign_keys.py`
- `backend/app/db/session.py`
- `backend/alembic/env.py`
- `backend/FK_POLICIES_SUMMARY.md`

Expected outcome:

- checklist becomes an honest FK/database-integrity document
- historical counts are preserved only as snapshot data
- SQLite-centric helper-script limitations are made explicit
- the next low-risk production-docs target shifts to `ops/README.md`
