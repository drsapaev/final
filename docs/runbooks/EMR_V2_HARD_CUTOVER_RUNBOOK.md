# EMR v2 Hard-Cutover Runbook

## Purpose
- Make `EMR v2` the only canonical EMR flow.
- Enforce one canonical EMR per clinical `visit_id`.
- Run schema upgrade, backfill legacy EMR rows into canonical storage, and verify invariants.

## What Was Already Rehearsed Locally
- Local Postgres DB: `clinicdb`
- Alembic upgraded successfully from `0001_baseline` to `0002_emr_v2_hard_cutover`
- Dry-run backfill completed successfully
- Live backfill completed successfully with `EMR_LEGACY_WRITE_FREEZE=1`
- Verification passed after live run
- Local result contained `0` legacy EMR rows, so it was a clean operational rehearsal rather than a data migration

## Preconditions
- Maintenance window is open
- Backend code with EMR v2 hard-cutover changes is deployed
- Frontend code with canonical `visit_id` handling is deployed
- You have DB access and admin API access
- You have a database backup taken outside this repo workflow

## One-Command Runner
From `backend/` you can run the whole sequence with one command:

```powershell
python scripts/run_emr_cutover.py --pretty
```

What it does:
- creates a `pg_dump` backup into `backend/backups/`
- sets `EMR_LEGACY_WRITE_FREEZE=1` for the cutover process
- runs `alembic upgrade head`
- runs `verify -> dry-run -> live -> verify`
- exits non-zero if the final verification is not green

Optional batched mode:

```powershell
python scripts/run_emr_cutover.py --pretty --limit 100
```

## Step 1: Schema Upgrade
From `backend/`:

```powershell
alembic upgrade head
```

Expected result:
- Alembic revision becomes `0002_emr_v2_hard_cutover`
- `emr_migration_ledger` table exists
- `prescriptions.visit_id`, `prescriptions.emr_record_id` exist
- `files.visit_id`, `files.emr_record_id` exist

## Step 2: Preflight Verification
From `backend/`:

```powershell
python scripts/emr_cutover_ops.py verify --pretty
```

Read these fields carefully:
- `checks.migration_completeness.legacy_total`
- `checks.migration_completeness.failed`
- `checks.canonical_uniqueness.duplicate_visit_records`
- `checks.canonical_uniqueness.missing_specialty`
- `checks.canonical_uniqueness.missing_specialty_data`
- `checks.referential_integrity.prescriptions_missing_canonical_refs`
- `checks.referential_integrity.files_missing_canonical_refs`

## Step 3: Enable Legacy Write Freeze
Set this before live backfill:

```powershell
$env:EMR_LEGACY_WRITE_FREEZE='1'
```

Production note:
- This must be set in the real backend process environment, not only in your shell.
- Legacy appointment-based EMR writes must reject during the cutover window.

## Step 4: Dry-Run Backfill
From `backend/`:

```powershell
python scripts/emr_cutover_ops.py dry-run --pretty
```

Optional batch rehearsal:

```powershell
python scripts/emr_cutover_ops.py dry-run --limit 100 --pretty
```

Proceed only if:
- `failed == 0`
- error list is empty or fully understood
- projected `rebound_prescriptions` and `rebound_files` counts look reasonable

## Step 5: Live Backfill
From `backend/`:

```powershell
python scripts/emr_cutover_ops.py live --pretty
```

Optional batched rollout:

```powershell
python scripts/emr_cutover_ops.py live --limit 100 --pretty
```

Repeat batched runs until:
- `processed == migrated + skipped + failed`
- no unexpected failures remain

## Step 6: Post-Cutover Verification
From `backend/`:

```powershell
python scripts/emr_cutover_ops.py verify --pretty
```

Success criteria:
- `passed == true`
- `failed == 0`
- `untracked_legacy_rows == 0`
- `duplicate_visit_records == 0`
- `missing_specialty == 0`
- `missing_specialty_data == 0`
- `duplicate_revision_versions == 0`
- `prescriptions_missing_canonical_refs == 0`
- `files_missing_canonical_refs == 0`

## Step 7: API-Level Verification
Check admin endpoints with an admin token:

```text
POST /api/v1/admin/migration/emr-cutover/backfill?dry_run=true
POST /api/v1/admin/migration/emr-cutover/backfill?dry_run=false
GET  /api/v1/admin/migration/emr-cutover/verification
```

Check specialist flow contract:
- open cardiology, dermatology, dentistry, lab
- ensure EMR opens only with canonical `visit_id`
- ensure new EMR payload contains `data.specialty`
- ensure `data.specialty_data` is always an object

## Step 8: Observation Window
For 7 days after cutover monitor:
- shim usage
- missing `visit_id` contract errors
- autosave/sign conflict spikes
- failed ledger rows
- duplicate EMR prevention hits
- prescriptions/files without canonical refs

## Rollback Boundary
- After live backfill starts, do not switch runtime writes back to legacy `emr`
- If something breaks, use forward-fix on canonical v2 or temporary maintenance mode

## Quick Commands
From `backend/`:

```powershell
python scripts/run_emr_cutover.py --pretty

python scripts/emr_cutover_ops.py verify --pretty
python scripts/emr_cutover_ops.py dry-run --pretty
$env:EMR_LEGACY_WRITE_FREEZE='1'
python scripts/emr_cutover_ops.py live --pretty
```
