# Clinic Operator Checklist

## Scope
- One-page checklist for clinic-host, on-prem, or VPS-hosted isolated deployments.
- Use the helper scripts directly. Do not improvise new setup flows.

## Before You Start
- Confirm `APP_ENV`, `APP_ROOT`, `APP_HOST`, `BACKEND_URL`, and `PUBLIC_URL`.
- Confirm `DATABASE_URL` points to the intended clinic database only.
- Confirm `.env.clinic-lifecycle` or `LIFECYCLE_ENV_FILE` is loaded.
- Confirm you know where backup artifacts are written.
- Confirm you have a rollback ref for update rehearsals.
- Confirm frontend runtime expectation is `same-origin` by default.
- Only allow split-origin when `FRONTEND_EXPECT_SPLIT_ORIGIN=1` is set intentionally.
- Confirm update source is an approved release artifact or a ref imported from it.

## Fresh Install
Run:
```bash
python3 ops/vps/scripts/smoke_fresh_install.py
```

PASS signals:
- `PASS: health_check completed successfully`
- `PASS: frontend_runtime_probe completed successfully`
- `PASS: smoke_fresh_install completed successfully`
- `CURRENT_ORIGIN=...`
- `RESOLVED_API_ORIGIN=...`
- `RESOLVED_WS_ORIGIN=...`
- `SETUP_BRANCH_ID=...`
- `SETUP_ADMIN_USER_ID=...`
- `SETUP_ACTIVATION_APPLIED=True|False`
- `GET /api/v1/setup/status` becomes `{"initialized": true}`

FAIL signals that stop rollout:
- any line starting with `FAIL:`
- `setup/status` is already initialized before first-run setup
- `POST /api/v1/setup/initialize` returns non-200
- frontend runtime probe resolves API or WS to an old build-time origin
- login smoke fails
- repeat setup does not return `409`

## Backup
Run:
```bash
python3 ops/vps/scripts/backup_db.py
```

PASS signals:
- `PASS: backup_db created ...`
- `BACKUP_FILE=...`

FAIL signals:
- backup file missing or empty
- `pg_dump` fails
- wrong database target in env

## Restore
Run:
```bash
python3 ops/vps/scripts/restore_db.py
```

PASS signals:
- `PASS: restore_db restored ...`
- `RESTORED_BACKUP_FILE=...`
- `RESTORE_DATABASE_URL=...`

FAIL signals:
- backup file not found
- restore target missing or wrong
- `pg_restore` / `psql` fails

## Update
Run:
```bash
UPDATE_RELEASE_REF=<approved-release-ref-or-imported-artifact-ref> \
ROLLBACK_REF=<baseline-ref> \
python3 ops/vps/scripts/run_update_rehearsal.py
```

PASS signals:
- `PASS: run_update_rehearsal completed successfully`
- `UPDATE_BACKUP_FILE=...`
- `PASS: run_migrations completed successfully`
- `PASS: frontend_runtime_probe completed successfully`
- `CURRENT_ORIGIN=...`
- `RESOLVED_API_ORIGIN=...`
- `RESOLVED_WS_ORIGIN=...`
- `PASS: smoke_post_update completed successfully`
- `PASS: health_check completed successfully`

FAIL signals:
- any `FAIL:`
- migrations fail
- health fails
- frontend runtime probe resolves API or WS to a stale origin
- login smoke fails
- rollback fails after update failure

Offline update import flow:
```bash
python3 ops/vps/scripts/import_release_artifact.py --artifact-file /path/to/clinic-release.zip
```

Use the emitted `IMPORTED_RELEASE_REF=...` as `UPDATE_RELEASE_REF`.

## Rollback
Run:
```bash
ROLLBACK_REF=<baseline-ref> \
python3 ops/vps/scripts/rollback_release.py
```

PASS signals:
- `PASS: rollback_release restored ...`
- follow-up `health_check.py` passes
- follow-up `smoke_post_update.py` passes

FAIL signals:
- rollback ref missing
- git checkout fails
- deploy fails after checkout

## Stop Conditions
Stop the rollout immediately if:
- any script prints `FAIL:`
- backup file is missing
- migrations do not reach head
- setup becomes available on an initialized instance
- restore target is not isolated
- rollback cannot restore a known-good release
