# Clinic Backup / Restore Rehearsal Runbook

## Purpose
- Prove that backups are restorable, not just creatable.
- Restore into a separate database or separate host.
- Confirm the restored instance behaves like the original initialized clinic.

## Preconditions
- A backup exists for the clinic deployment.
- A separate target database or separate target host is available.
- The restore target is not the live production database.
- A backend process pointed at the restore target database is reachable at `RESTORE_BACKEND_URL`.
- A public URL for that restored target is reachable at `RESTORE_PUBLIC_URL`.
- `RESTORE_DATABASE_URL`, `RESTORE_BACKEND_URL`, and `RESTORE_PUBLIC_URL` point at the isolated restore target.
- A lifecycle env file such as `.env.clinic-lifecycle` is available with admin login credentials or equivalent `SMOKE_LOGIN_*` / `SETUP_ADMIN_*` variables.

## Backup and Restore Command

```bash
RESTORE_DATABASE_URL=postgresql+psycopg://restore_user:restore_pwd@127.0.0.1:5432/restore_db \
RESTORE_BACKEND_URL=http://127.0.0.1:18001 \
RESTORE_PUBLIC_URL=http://127.0.0.1:18001 \
SMOKE_REQUIRE_LOGIN=1 \
python3 ops/vps/scripts/run_backup_restore_rehearsal.py
```

What the wrapper does:
- creates a fresh backup with `backup_db.py`
- restores it with `restore_db.py`
- runs `health_check.py` against the restore target
- runs `smoke_post_update.py` against the restore target, including frontend runtime origin proof

## Manual Restore Flow

If you want to inspect the steps one by one:

```bash
python3 ops/vps/scripts/backup_db.py
python3 ops/vps/scripts/restore_db.py \
  --backup-file <backup-file> \
  --target-database-url <restore-database-url>
PUBLIC_URL=http://127.0.0.1:18001 \
BACKEND_URL=http://127.0.0.1:18001 \
EXPECTED_SETUP_INITIALIZED=1 \
python3 ops/vps/scripts/health_check.py

PUBLIC_URL=http://127.0.0.1:18001 \
BACKEND_URL=http://127.0.0.1:18001 \
SMOKE_REQUIRE_LOGIN=0 \
python3 ops/vps/scripts/smoke_post_update.py
```

## Acceptance Criteria
- The backup can be restored into a clean target.
- The restored instance is usable.
- No live clinic data was overwritten during rehearsal.
- The same restore path remains valid regardless of whether the current app build came from an online release source or an offline approved artifact.

## Evidence To Save
- Backup filename
- Restore target database name
- Restore command output
- Smoke results on the restored target, including current/api/ws origin lines
