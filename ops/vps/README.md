# VPS Host Rollout Kit

This kit deploys the already-working clinic contour to a Linux VPS without Docker:

- PostgreSQL on the host
- Backend via `systemd`
- Frontend as static `dist/` served by Nginx
- EMR cutover run against the VPS database after deploy

This is a deployment transport, not a separate product mode. The target model remains:

- one isolated deployment per clinic
- one PostgreSQL database per clinic deployment
- one runtime per clinic deployment
- first-run business initialization inside the deployed app via `/setup`

The same post-deploy `/setup` flow is intended to support both VPS-hosted and on-prem clinic-host installations.

Default workstation access remains browser/LAN first:
- no separate backend on workstations
- no separate PostgreSQL on workstations
- any thin launcher is optional convenience only

## Layout

- `backend.env.sample`: backend environment template for staging or production
- `frontend.env.sample`: optional frontend override template for split-origin deployments
- `clinic_lifecycle.env.sample`: shared env template for lifecycle scripts and rehearsals
- `scripts/build_release_artifact.py`: build an approved release artifact for online or offline delivery
- `scripts/import_release_artifact.py`: import an approved release artifact into the local clinic host repo
- `nginx/clinic.conf.template`: Nginx site template
- `systemd/clinic-backend.service.template`: backend service template
- `scripts/bootstrap_postgres.sh`: create DB user/database
- `scripts/backup_db.py`: create a PostgreSQL backup artifact
- `scripts/restore_db.py`: restore a backup into a target PostgreSQL database
- `scripts/deploy_release.py`: deploy a checked-out release with migrations skipped
- `scripts/run_migrations.py`: run Alembic to head
- `scripts/health_check.py`: backend/frontend/setup smoke check
- `scripts/smoke_fresh_install.py`: initialize a fresh clinic deployment and smoke it
- `scripts/smoke_post_update.py`: smoke an initialized deployment after update
- `scripts/rollback_release.py`: rollback to a previous checkout and redeploy
- `scripts/run_update_rehearsal.py`: backup + deploy + migrate + smoke + rollback wrapper
- `scripts/run_backup_restore_rehearsal.py`: backup + restore + smoke wrapper
- `scripts/deploy_host.sh`: install deps, build frontend, migrate backend, render configs
- `scripts/run_cutover.sh`: run `run_emr_cutover.py` on VPS
- `scripts/check_health.sh`: smoke-check backend/frontend

## Expected Host Paths

- App root: `/opt/clinic`
- Backend: `/opt/clinic/backend`
- Frontend: `/opt/clinic/frontend`
- Frontend dist: `/opt/clinic/frontend/dist`
- Backend env: `/opt/clinic/backend/.env.production` or `.env.staging`

## Minimal Ubuntu/Debian Prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm nginx postgresql postgresql-contrib
```

## Typical Staging Rollout

```bash
cd /opt/clinic

cp ops/vps/backend.env.sample backend/.env.staging
cp ops/vps/frontend.env.sample frontend/.env.staging
cp ops/vps/clinic_lifecycle.env.sample .env.clinic-lifecycle

# Generate a unique DB password, then put it into backend/.env.staging
# and .env.clinic-lifecycle DATABASE_URL before deploy.
DB_PASSWORD="$(openssl rand -base64 24)"

sudo bash ops/vps/scripts/bootstrap_postgres.sh clinic_staging "$DB_PASSWORD" clinic_staging

sudo APP_ENV=staging \
  APP_HOST=staging.example.com \
  APP_ROOT=/opt/clinic \
  RUN_AS_USER=$USER \
  bash ops/vps/scripts/deploy_host.sh

sudo APP_ENV=staging APP_ROOT=/opt/clinic bash ops/vps/scripts/run_cutover.sh
PUBLIC_URL=https://staging.example.com \
BACKEND_URL=http://127.0.0.1:18000 \
python3 ops/vps/scripts/health_check.py
```

For normal clinic deployments, the frontend should use same-origin runtime resolution for `/api` and `/ws`. Set `VITE_API_BASE_URL` only when you intentionally point the frontend at a separate API origin. The smoke scripts now emit:

- `CURRENT_ORIGIN=...`
- `RESOLVED_API_ORIGIN=...`
- `RESOLVED_WS_ORIGIN=...`

Treat any unexpected old build-time origin as a rollout blocker.
`localhost` is reserved for internal health/backend checks and loopback service access, not as the official clinic URL.

After infrastructure deploy completes, complete first-run setup with:

```bash
python3 ops/vps/scripts/smoke_fresh_install.py
```

## Typical Production Rollout

> Only run this section after a separate VPS staging contour has passed smoke validation, EMR cutover, and a short soak window. Production rollout stays blocked until staging is green.

```bash
cd /opt/clinic

cp ops/vps/backend.env.sample backend/.env.production
cp ops/vps/frontend.env.sample frontend/.env.production

# Generate a unique DB password, then put it into backend/.env.production
# DATABASE_URL before deploy.
DB_PASSWORD="$(openssl rand -base64 24)"

sudo bash ops/vps/scripts/bootstrap_postgres.sh clinic_prod "$DB_PASSWORD" clinic_prod

sudo APP_ENV=production \
  APP_HOST=clinic.example.com \
  APP_ROOT=/opt/clinic \
  RUN_AS_USER=$USER \
  bash ops/vps/scripts/deploy_host.sh

sudo APP_ENV=production APP_ROOT=/opt/clinic bash ops/vps/scripts/run_cutover.sh
PUBLIC_URL=https://clinic.example.com \
BACKEND_URL=http://127.0.0.1:18000 \
python3 ops/vps/scripts/health_check.py
```

## Lifecycle Commands

Fresh install smoke:

```bash
python3 ops/vps/scripts/smoke_fresh_install.py
```

Post-update smoke:

```bash
python3 ops/vps/scripts/smoke_post_update.py
```

Update rehearsal:

```bash
UPDATE_RELEASE_REF=<approved-release-ref-or-imported-artifact-ref> \
SMOKE_REQUIRE_LOGIN=1 \
python3 ops/vps/scripts/run_update_rehearsal.py
```

Approved release artifact workflow:

```bash
python3 ops/vps/scripts/build_release_artifact.py --ref <approved-release-ref>
python3 ops/vps/scripts/import_release_artifact.py --artifact-file /path/to/clinic-release.zip
```

Offline clinics use the same artifact file after copying it to the host. The imported artifact prints `IMPORTED_RELEASE_REF=...`, which can be passed into `UPDATE_RELEASE_REF`.

Backup / restore rehearsal:

```bash
RESTORE_DATABASE_URL=postgresql+psycopg://restore_user:restore_pwd@127.0.0.1:5432/restore_db \
RESTORE_BACKEND_URL=http://127.0.0.1:18001 \
RESTORE_PUBLIC_URL=http://127.0.0.1:18001 \
python3 ops/vps/scripts/run_backup_restore_rehearsal.py
```

## Notes

- Backend listens on `127.0.0.1:18000`; Nginx proxies public traffic to it.
- Frontend is served by Nginx from the built `dist/`.
- `deploy_host.sh` does not create TLS certificates. Use your normal Certbot or reverse-proxy workflow after the first Nginx start.
- `run_cutover.sh` expects `EMR_LEGACY_WRITE_FREEZE=1` inside the backend env file.
- Landing/marketing flows must not be used as the primary activation/bootstrap path for a fresh clinic deployment; `/setup` is the intended first-run path inside the instance.
