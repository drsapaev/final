# VPS Host Rollout Runbook

## Goal
- Move the already validated clinic contour from local staging to a Linux VPS.
- Keep the deployment simple and observable:
  - PostgreSQL on host
  - Backend via `systemd`
  - Frontend static build via Nginx
  - EMR cutover run after deploy

## Files
- [ops/vps/README.md](/C:/final/ops/vps/README.md)
- [ops/vps/backend.env.sample](/C:/final/ops/vps/backend.env.sample)
- [ops/vps/frontend.env.sample](/C:/final/ops/vps/frontend.env.sample)
- [ops/vps/nginx/clinic.conf.template](/C:/final/ops/vps/nginx/clinic.conf.template)
- [ops/vps/systemd/clinic-backend.service.template](/C:/final/ops/vps/systemd/clinic-backend.service.template)
- [ops/vps/scripts/bootstrap_postgres.sh](/C:/final/ops/vps/scripts/bootstrap_postgres.sh)
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
```

Edit:
- `backend/.env.staging`
- `frontend/.env.staging`

Minimum edits:
- real DB URL
- real secrets
- real host/domain
- `EMR_LEGACY_WRITE_FREEZE=1`

## Bootstrap Postgres

```bash
sudo bash ops/vps/scripts/bootstrap_postgres.sh clinic_staging change-me clinic_staging
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
bash ops/vps/scripts/check_health.sh https://staging.example.com http://127.0.0.1:18000
```

Then manually verify:
- login
- cardiology EMR
- dermatology EMR
- dentistry EMR
- lab panel
- doctor-history

## Promote To Production

> Only run production rollout after the separate VPS staging contour has passed smoke validation, EMR cutover, and a short soak window. Do not promote directly from local acceptance.

- Duplicate `.env.staging` into `.env.production`
- Switch hostnames/domains
- Point production DB URL to production database
- Re-run `deploy_host.sh` with `APP_ENV=production`
- Re-run `run_cutover.sh` against production only during maintenance window
