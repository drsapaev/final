# VPS Host Rollout Kit

This kit deploys the already-working clinic contour to a Linux VPS without Docker:

- PostgreSQL on the host
- Backend via `systemd`
- Frontend as static `dist/` served by Nginx
- EMR cutover run against the VPS database after deploy

## Layout

- `backend.env.sample`: backend environment template for staging or production
- `frontend.env.sample`: frontend Vite environment template
- `nginx/clinic.conf.template`: Nginx site template
- `systemd/clinic-backend.service.template`: backend service template
- `scripts/bootstrap_postgres.sh`: create DB user/database
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

# edit both env files first

sudo bash ops/vps/scripts/bootstrap_postgres.sh clinic_staging clinic_staging_pwd clinic_staging

sudo APP_ENV=staging \
  APP_HOST=staging.example.com \
  APP_ROOT=/opt/clinic \
  RUN_AS_USER=$USER \
  bash ops/vps/scripts/deploy_host.sh

sudo APP_ENV=staging APP_ROOT=/opt/clinic bash ops/vps/scripts/run_cutover.sh
bash ops/vps/scripts/check_health.sh https://staging.example.com http://127.0.0.1:18000
```

## Typical Production Rollout

> Only run this section after a separate VPS staging contour has passed smoke validation, EMR cutover, and a short soak window. Production rollout stays blocked until staging is green.

```bash
cd /opt/clinic

cp ops/vps/backend.env.sample backend/.env.production
cp ops/vps/frontend.env.sample frontend/.env.production

# edit both env files first

sudo bash ops/vps/scripts/bootstrap_postgres.sh clinic_prod change-me clinic_prod

sudo APP_ENV=production \
  APP_HOST=clinic.example.com \
  APP_ROOT=/opt/clinic \
  RUN_AS_USER=$USER \
  bash ops/vps/scripts/deploy_host.sh

sudo APP_ENV=production APP_ROOT=/opt/clinic bash ops/vps/scripts/run_cutover.sh
bash ops/vps/scripts/check_health.sh https://clinic.example.com http://127.0.0.1:18000
```

## Notes

- Backend listens on `127.0.0.1:18000`; Nginx proxies public traffic to it.
- Frontend is served by Nginx from the built `dist/`.
- `deploy_host.sh` does not create TLS certificates. Use your normal Certbot or reverse-proxy workflow after the first Nginx start.
- `run_cutover.sh` expects `EMR_LEGACY_WRITE_FREEZE=1` inside the backend env file.
