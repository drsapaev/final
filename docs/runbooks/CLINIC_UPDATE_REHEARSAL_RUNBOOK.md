# Clinic Update Rehearsal Runbook

## Purpose
- Prove that an already initialized clinic deployment can be upgraded safely.
- Ensure updates do not bring back `/setup`.
- Verify data, login, queue, and EMR survive deploy + migrations.

## Preconditions
- A clinic deployment is already initialized.
- Real clinic data exists in the database.
- A known-good backup has been created immediately before the rehearsal.
- The previous approved release artifact or checkout is still available for rollback.
- `UPDATE_RELEASE_REF` points at the approved release to test.
- A lifecycle env file such as `.env.clinic-lifecycle` is available with admin login credentials or equivalent `SMOKE_LOGIN_*` / `SETUP_ADMIN_*` variables.

`UPDATE_RELEASE_REF` may come from:
- an approved GitHub or online release source
- an imported offline approved release artifact

## Update Rehearsal Command

```bash
UPDATE_RELEASE_REF=<approved-release-ref-or-imported-artifact-ref> \
ROLLBACK_REF=<baseline-ref> \
SMOKE_REQUIRE_LOGIN=1 \
python3 ops/vps/scripts/run_update_rehearsal.py
```

What the wrapper does:
- creates a fresh backup with `backup_db.py`
- deploys the approved release selected by `UPDATE_RELEASE_REF`
- runs `run_migrations.py`
- runs `health_check.py` with `EXPECTED_SETUP_INITIALIZED=1`
- runs `smoke_post_update.py`, which also emits `CURRENT_ORIGIN`, `RESOLVED_API_ORIGIN`, and `RESOLVED_WS_ORIGIN`
- rolls back automatically on failure

## Manual Verification After a Successful Rehearsal

```bash
PUBLIC_URL=https://clinic.example.com \
BACKEND_URL=http://127.0.0.1:18000 \
EXPECTED_SETUP_INITIALIZED=1 \
python3 ops/vps/scripts/health_check.py

PUBLIC_URL=https://clinic.example.com \
BACKEND_URL=http://127.0.0.1:18000 \
SMOKE_REQUIRE_LOGIN=1 \
python3 ops/vps/scripts/smoke_post_update.py
```

## Rollback Plan
- Keep the previous release and env snapshot until the update is proven.
- If the new release fails health or smoke checks, the wrapper rolls back to `ROLLBACK_REF`.
- If the database migration is not backward-safe, restore the pre-update backup into the target database before retrying.
- Re-run smoke checks after rollback.

If the clinic is local-only:
- import the approved release artifact first
- use the emitted `IMPORTED_RELEASE_REF` as `UPDATE_RELEASE_REF`

## Acceptance Criteria
- Updated deployment is initialized and stable.
- `/setup` remains inaccessible as an onboarding route.
- All key clinician and admin flows still work.
- A rollback path exists and is documented before the upgrade is attempted.

## Evidence To Save
- Pre-update backup reference
- Migration output
- Post-update health result
- Smoke evidence for login, origin resolution, and a live clinical workflow
- Rollback evidence if the rehearsal fails
