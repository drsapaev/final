# Clinic State Separation Audit

## Purpose
- Verify that release state, runtime config, data, uploads, logs, and backups are separated.
- Prevent one clinic deployment from accidentally sharing another clinic's operational state.

## State Buckets

1. Release code
- Source checkout or approved release artifact.
- Must be unique per deployable version.

2. Environment and secrets
- `.env.production`, `.env.staging`, or clinic-specific env files.
- Must never be reused across unrelated clinics.

3. Database
- One PostgreSQL database per clinic deployment.
- One connection string per clinic deployment.

4. Uploads and files
- Runtime uploads, attachments, generated exports, and static media.
- Must have a clinic-specific storage root.

5. Logs
- App logs, proxy logs, and scheduler logs.
- Must be isolated by host or deployment path.

6. Backups
- Backup directory, retention, and restore target.
- Must be named per clinic deployment.

## Audit Checklist

- Confirm the deployment has exactly one active `DATABASE_URL`.
- Confirm the clinic host / domain is clinic-specific.
- Confirm the upload directory is clinic-specific.
- Confirm backup files are written outside the source tree.
- Confirm rollback artifacts for the previous release are still present during update rehearsal.
- Confirm no shared setup-state table exists.
- Confirm `/setup` uses SSOT-backed initialization only.

## Quick Commands

Check setup state:
```bash
python3 ops/vps/scripts/health_check.py
```

Check health:
```bash
PUBLIC_URL=http://clinic.example.com \
BACKEND_URL=http://127.0.0.1:18000 \
EXPECTED_SETUP_INITIALIZED=1 \
python3 ops/vps/scripts/health_check.py
```

Inspect env:
```bash
grep -E 'DATABASE_URL|APP_HOST|APP_ENV|BACKUP_' backend/.env.production
```

Run a fresh-install smoke against a clean deployment:
```bash
SETUP_PAYLOAD_FILE=/opt/clinic/setup.json \
python3 ops/vps/scripts/smoke_fresh_install.py
```

Run an update rehearsal:
```bash
UPDATE_RELEASE_REF=<approved-release-ref-or-imported-artifact-ref> \
python3 ops/vps/scripts/run_update_rehearsal.py
```

## Acceptance Criteria
- Every mutable runtime bucket is clinic-specific or deployment-specific.
- No shared mutable runtime state is required for more than one clinic deployment.
- Rollback and restore do not depend on hidden local assumptions.
