# W2D Production Readiness Checklist Verification

## Summary

This was a bounded docs-vs-code audit for:

- `backend/PRODUCTION_READINESS_CHECKLIST.md`

The goal was not to redesign the underlying FK/integrity scripts. The goal was
to stop a narrow database-integrity checklist from reading like the current
whole-system production approval for the project.

## Findings

### The checklist was really an FK/schema-integrity document

- most of the content was about:
  - FK policy hardening
  - orphaned-record cleanup
  - SQLite FK enforcement
  - migration validation
- but the title and closing language still read like a broad current
  `Production Ready` verdict for the whole backend

### Snapshot counts and cleanup totals were historical, not universal truth

- the document still presented fixed numbers such as:
  - `88` tables
  - `99` FK constraints
  - `28` cleaned orphaned records
- those are point-in-time database observations, not stable repo-wide truths

### The validation scripts are not current engine-agnostic deploy gates

Current local verification showed important caveats:

- `python validate_production_readiness.py`
  - failed against the current local PostgreSQL URL because it issues SQLite
    `PRAGMA` statements and then hit Windows console encoding issues while
    reporting the failure
- `python verify_fk_enforcement.py`
  - explicitly targets SQLite behavior and also failed in the current local
    Windows console path before completing a useful warning flow
- the honest docs move was to keep those scripts visible as FK/integrity
  helpers while removing the implication that they are current universal
  predeploy gates

## What changed

- reframed `backend/PRODUCTION_READINESS_CHECKLIST.md` as an archived
  FK/database-integrity checklist with current caveats
- removed the current-looking whole-system `Production Ready` framing
- preserved the useful helper-script list and migration guidance
- downgraded snapshot counts and cleanup totals to historical data
- added explicit caveats about current PostgreSQL and Windows console behavior
  for the readiness helper scripts

## Evidence used

- `backend/PRODUCTION_READINESS_CHECKLIST.md`
- `backend/validate_production_readiness.py`
- `backend/verify_fk_enforcement.py`
- `backend/validate_fk_policies.py`
- `backend/cleanup_orphaned_records.py`
- `backend/app/scripts/audit_foreign_keys.py`
- `backend/app/db/session.py`
- `backend/alembic/env.py`
- `backend/FK_POLICIES_SUMMARY.md`

## Verification

- `python validate_production_readiness.py`
- `python verify_fk_enforcement.py`
- `pytest tests/test_openapi_contract.py -q`

## Recommended next step

Continue the neighboring ops/deployment docs audit with:

- `ops/README.md`

Follow-on companion:

- `ops/.env.example`

Why:

- they still carry visible `AUTH_SECRET`, compose-default, and local/dev-facing
  deployment assumptions
- after the backend-side production docs are normalized, the next honest
  low-risk follow-up is the ops-facing entrypoint for the same deployment story
