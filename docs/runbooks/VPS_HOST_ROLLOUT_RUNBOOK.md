# VPS Host Rollout Runbook

## Goal
- Move the already validated clinic contour from local staging to a Linux VPS.
- Keep the deployment simple and observable:
  - PostgreSQL on host
  - Backend via `systemd`
  - Frontend static build via Nginx
  - EMR cutover run after deploy
- This runbook documents one isolated-deployment option (`VPS-hosted`). The same application-level first-run `/setup` flow is intended to be reused for clinic-host / on-prem installs.

## Files
- [ops/vps/README.md](/C:/final/ops/vps/README.md)
- [ops/vps/backend.env.sample](/C:/final/ops/vps/backend.env.sample)
- [ops/vps/frontend.env.sample](/C:/final/ops/vps/frontend.env.sample)
- [ops/vps/clinic_lifecycle.env.sample](/C:/final/ops/vps/clinic_lifecycle.env.sample)
- [ops/vps/nginx/clinic.conf.template](/C:/final/ops/vps/nginx/clinic.conf.template)
- [ops/vps/systemd/clinic-backend.service.template](/C:/final/ops/vps/systemd/clinic-backend.service.template)
- [ops/vps/scripts/bootstrap_postgres.sh](/C:/final/ops/vps/scripts/bootstrap_postgres.sh)
- [ops/vps/scripts/backup_db.py](/C:/final/ops/vps/scripts/backup_db.py)
- [ops/vps/scripts/restore_db.py](/C:/final/ops/vps/scripts/restore_db.py)
- [ops/vps/scripts/deploy_release.py](/C:/final/ops/vps/scripts/deploy_release.py)
- [ops/vps/scripts/run_migrations.py](/C:/final/ops/vps/scripts/run_migrations.py)
- [ops/vps/scripts/health_check.py](/C:/final/ops/vps/scripts/health_check.py)
- [ops/vps/scripts/smoke_fresh_install.py](/C:/final/ops/vps/scripts/smoke_fresh_install.py)
- [ops/vps/scripts/smoke_post_update.py](/C:/final/ops/vps/scripts/smoke_post_update.py)
- [ops/vps/scripts/rollback_release.py](/C:/final/ops/vps/scripts/rollback_release.py)
- [ops/vps/scripts/run_update_rehearsal.py](/C:/final/ops/vps/scripts/run_update_rehearsal.py)
- [ops/vps/scripts/run_backup_restore_rehearsal.py](/C:/final/ops/vps/scripts/run_backup_restore_rehearsal.py)
- [ops/vps/scripts/build_release_artifact.py](/C:/final/ops/vps/scripts/build_release_artifact.py)
- [ops/vps/scripts/import_release_artifact.py](/C:/final/ops/vps/scripts/import_release_artifact.py)
- [ops/vps/scripts/deploy_host.sh](/C:/final/ops/vps/scripts/deploy_host.sh)
- [ops/vps/scripts/run_cutover.sh](/C:/final/ops/vps/scripts/run_cutover.sh)
- [ops/vps/scripts/check_health.sh](/C:/final/ops/vps/scripts/check_health.sh)

## Prepare VPS

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm nginx postgresql postgresql-contrib
sudo mkdir -p /opt/clinic
sudo chown -R $USER:$USER /opt/clinic
```

Clone or copy the repo into `/opt/clinic`.

## Configure Staging On VPS

```bash
cd /opt/clinic
cp ops/vps/backend.env.sample backend/.env.staging
cp ops/vps/frontend.env.sample frontend/.env.staging
cp ops/vps/clinic_lifecycle.env.sample .env.clinic-lifecycle
```

Edit:
- `backend/.env.staging`
- `frontend/.env.staging`
- `.env.clinic-lifecycle` for lifecycle commands

For the normal same-origin deployment path, `frontend/.env.staging` does not need a clinic-specific API domain. The built frontend now prefers current-origin runtime resolution for `/api` and `/ws`, and the smoke scripts emit:

- `CURRENT_ORIGIN=...`
- `RESOLVED_API_ORIGIN=...`
- `RESOLVED_WS_ORIGIN=...`

Any stale build-time origin in those probe lines is a rollout blocker.

Minimum edits:
- real DB URL
- real secrets
- real host/domain
- `EMR_LEGACY_WRITE_FREEZE=1`

## Bootstrap Postgres

```bash
DB_PASSWORD="$(openssl rand -base64 24)"
sudo bash ops/vps/scripts/bootstrap_postgres.sh clinic_staging "$DB_PASSWORD" clinic_staging
```

## Deploy

```bash
sudo APP_ENV=staging \
  APP_HOST=staging.example.com \
  APP_ROOT=/opt/clinic \
  RUN_AS_USER=$USER \
  bash ops/vps/scripts/deploy_host.sh
```

## Run EMR Cutover

```bash
sudo APP_ENV=staging APP_ROOT=/opt/clinic bash ops/vps/scripts/run_cutover.sh
```

Expected success:
- `passed == true`
- `failed == 0`
- `duplicate_visit_records == 0`
- `missing_specialty == 0`
- `missing_specialty_data == 0`
- `prescriptions_missing_canonical_refs == 0`
- `files_missing_canonical_refs == 0`

## Verify

```bash
PUBLIC_URL=https://staging.example.com \
BACKEND_URL=http://127.0.0.1:18000 \
python3 ops/vps/scripts/health_check.py
```

```bash
SETUP_PAYLOAD_FILE=/opt/clinic/setup.json \
python3 ops/vps/scripts/smoke_fresh_install.py
```
You can replace the payload file with `SETUP_*` env vars if you want inline setup config.

Then manually verify:
- login
- cardiology EMR
- dermatology EMR
- dentistry EMR
- lab panel
- doctor-history

For offline-capable updates later:
- build or receive an approved release artifact
- import it on the host
- deploy it through `run_update_rehearsal.py` using the imported release ref

## Promote To Production

> Only run production rollout after the separate VPS staging contour has passed smoke validation, EMR cutover, and a short soak window. Do not promote directly from local acceptance.

- Duplicate `.env.staging` into `.env.production`
- Switch hostnames/domains
- Point production DB URL to production database
- Re-run `deploy_host.sh` with `APP_ENV=production`
- Re-run `run_cutover.sh` against production only during maintenance window
- Verify with `smoke_post_update.py` after deploy/migrations before handing the instance over
