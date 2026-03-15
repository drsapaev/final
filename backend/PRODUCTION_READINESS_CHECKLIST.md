# Production Readiness Checklist

Reviewed For Drift: 2026-03-14
Historical Status: archived FK/database-integrity checklist, not a current whole-system production approval

## How to use this file

This file is still useful, but its real scope is narrower than the title
suggests.

It primarily captures FK hardening, orphan-cleanup, and schema-integrity
guidance. It should not be read as the current go-live verdict for the whole
backend.

Use current execution status from:

- `C:/final/docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
- `C:/final/docs/status/OPENHANDS_TASK_BACKLOG.md`

Current repo-backed verification baseline:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- `pytest -q` -> `850 passed, 3 skipped`

## Historical Snapshot Focus

This checklist comes from the FK hardening / database-integrity track and was
focused on:

- explicit FK policies
- orphaned record cleanup
- SQLite FK enforcement
- migration hygiene
- database schema validation helpers

It was never a complete runtime, security, payments, frontend, queue, EMR, or
ops-readiness matrix for the whole system.

## Historical Snapshot Findings

These items remain useful as archived context, but they are snapshot-time
claims rather than current universal truth:

- FK policy hardening was completed for the schema that existed at the time
- orphaned-record cleanup was run against a specific database state
- schema counts such as `88 tables`, `99 FK constraints`, and `28 cleaned
  records` were point-in-time observations
- those counts can change by branch, database engine, migration state, and
  seeded data

Historical recorded examples:

- explicit `ondelete` policies were added across a large FK surface
- SQLite FK enforcement was wired through the session and Alembic paths
- orphaned records were cleaned in the then-current database snapshot

## Repo-Backed Helper Scripts Still Present

These helper scripts currently exist in the repo:

```powershell
python cleanup_orphaned_records.py
python validate_production_readiness.py
python verify_fk_enforcement.py
python validate_fk_policies.py
python app/scripts/audit_foreign_keys.py
```

Related supporting files also exist:

- `backend/FK_POLICIES_SUMMARY.md`
- `backend/app/db/session.py`
- `backend/alembic/env.py`
- `backend/app/scripts/ensure_admin.py`
- `backend/create_test_data.py`
- `backend/create_medical_records_table.py`

## Current Caveats

### This checklist is database-integrity oriented, not full production readiness

It is honest for FK/schema integrity work, but not for the whole system.

It does not by itself prove:

- runtime deployment safety
- compose/env correctness
- current auth/payment/queue/EMR behavior
- frontend/backend parity
- full operational readiness

### The validation scripts are not universal predeploy gates

Current local verification showed important limitations:

- `python validate_production_readiness.py`
  - does not complete cleanly against the current local PostgreSQL URL because
    it issues SQLite `PRAGMA` statements and then falls into Windows console
    encoding issues while reporting the failure
- `python verify_fk_enforcement.py`
  - explicitly targets SQLite behavior and also fails in the current local
    Windows console path before a useful warning is fully printed
- `python validate_fk_policies.py`
  - is still useful as a helper, but it also documents that SQLite schema
    introspection does not fully expose `ondelete` behavior

The honest takeaway:

- these scripts are helper diagnostics
- they are not current engine-agnostic, universal "deploy now" gates

## Safer Current Usage

### 1. Use the helper scripts for bounded FK/schema checks

Use the scripts when you specifically want FK or orphan-audit evidence and the
current database/driver context matches what the script expects.

### 2. Use migration hygiene for schema changes

```powershell
alembic revision --autogenerate -m "description"
alembic upgrade head --sql
alembic upgrade head
```

### 3. Use current repo verification for the live baseline

```powershell
pytest tests/test_openapi_contract.py -q
pytest -q
```

### 4. Use setup/runbook docs for deployment prep

Deployment-oriented docs now live more honestly in:

- `C:/final/backend/SETUP_PRODUCTION.md`
- `C:/final/backend/PRODUCTION_SETUP_SUMMARY.md`
- `C:/final/backend/PRODUCTION_READINESS_REPORT.md`

## Historical Data-Seeding Helpers

These commands still exist, but their presence should not be read as proof that
all product flows are currently validated end-to-end:

```powershell
python app/scripts/ensure_admin.py
python create_test_data.py
python create_medical_records_table.py
```

## Historical Statistics

Treat these as archived snapshot numbers, not current guaranteed counts:

- `88` tables
- `99` FK constraints
- approximately `45` CASCADE policies
- approximately `90` SET NULL policies
- `2` RESTRICT policies
- `28` cleaned orphaned records in one historical cleanup pass

## Reader Rule

If this checklist conflicts with current code, generated contracts, or the
master status docs:

- trust the current code and generated artifacts first
- trust `AI_FACTORY_OPENHANDS_MASTER_PLAN.md` over this file
- treat this checklist as historical FK/database guidance unless re-verified
