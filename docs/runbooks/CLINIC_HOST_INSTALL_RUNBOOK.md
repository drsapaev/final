# Clinic Host Install Runbook

## Scope
- First production-like install for a single clinic on an isolated deployment.
- Target transport: Linux clinic-host or on-prem host.
- Same lifecycle applies to VPS-hosted rollout, but this runbook is written for a clinic-owned host.

## Goals
- One clinic gets one isolated deployment.
- One deployment gets one PostgreSQL database.
- First-run business setup happens inside the deployed app at `/setup`.
- `/setup` must orchestrate existing SSOT entities only.
- The host machine is the only machine that runs backend, PostgreSQL, storage, and update tooling.
- Workstations use browser/LAN access by default and do not install their own backend or database.

## Preconditions
- Linux host prepared with SSH access and sudo.
- Git, Python 3.11, Node.js, npm, nginx, and PostgreSQL installed.
- Host DNS or internal name chosen for the clinic instance.
- Repository available on the target host.
- Backup directory created and writable.
- `backend/.env.production` and `frontend/.env.production` are ready to be edited.
- Optional first-run payload prepared as JSON, for example `SETUP_PAYLOAD_FILE=/opt/clinic/setup.json`.

## Installer Assistance Rules
- The installer may auto-detect the host machine candidate and prefill it for confirmation.
- The installer may auto-suggest the LAN URL from the detected host/IP, but the operator must confirm it before continuing.
- `localhost` is allowed only for internal health/backend checks and loopback service access.
- `localhost` must not be stored as the official clinic URL.
- If a LAN URL is not confirmed, the install must pause instead of guessing.

## Install Skeleton

1. Prepare host directories.
```bash
sudo mkdir -p /opt/clinic
sudo chown -R "$USER:$USER" /opt/clinic
```

2. Clone or copy the repository into `/opt/clinic`.

Workstations do not repeat this process. They only open the clinic LAN/public URL in a browser and sign in with their own account.

3. Create an isolated database for the clinic.
```bash
sudo bash ops/vps/scripts/bootstrap_postgres.sh clinic_host clinic_host_password clinic_host
```

4. Configure backend environment.
```bash
cp ops/vps/backend.env.sample backend/.env.production
```

Minimum values:
```env
APP_ENV=production
APP_HOST=clinic.internal.example
DATABASE_URL=postgresql://clinic_host:<db_password>@127.0.0.1:5432/clinic_host
# Generate a fresh value during install; do not commit or reuse examples.
SECRET_KEY=
BACKEND_CORS_ORIGINS=https://clinic.internal.example
ENSURE_ADMIN=0
ENSURE_ADMIN_ALLOW_INITIALIZED=0
```

5. Configure frontend environment.
```bash
cp ops/vps/frontend.env.sample frontend/.env.production
```

6. Deploy the application.
```bash
sudo APP_ENV=production \
  APP_HOST=clinic.internal.example \
  APP_ROOT=/opt/clinic \
  RUN_AS_USER="$USER" \
  bash ops/vps/scripts/deploy_host.sh
```

7. Smoke the fresh install and complete first-run setup.
```bash
SETUP_PAYLOAD_FILE=/opt/clinic/setup.json \
python3 ops/vps/scripts/smoke_fresh_install.py
```
You can also replace the payload file with `SETUP_*` env variables if you prefer inline config.
The smoke output must include:
- `PASS: frontend_runtime_probe completed successfully`
- `CURRENT_ORIGIN=...`
- `RESOLVED_API_ORIGIN=...`
- `RESOLVED_WS_ORIGIN=...`

8. Log in with the first admin account.
If login smoke was enabled, it already validated the admin credentials.

## Fresh Install Smoke Pack

Run these commands in order:

```bash
PUBLIC_URL=https://clinic.internal.example \
BACKEND_URL=http://127.0.0.1:18000 \
EXPECTED_SETUP_INITIALIZED=0 \
python3 ops/vps/scripts/health_check.py

SETUP_PAYLOAD_FILE=/opt/clinic/setup.json \
python3 ops/vps/scripts/smoke_fresh_install.py

PUBLIC_URL=https://clinic.internal.example \
BACKEND_URL=http://127.0.0.1:18000 \
EXPECTED_SETUP_INITIALIZED=1 \
python3 ops/vps/scripts/health_check.py
```

Repeat setup should fail:

```bash
SETUP_PAYLOAD_FILE=/opt/clinic/setup.json \
python3 ops/vps/scripts/smoke_fresh_install.py
```

Expected result on a second run:
- script exits `FAIL`
- `/api/v1/setup/initialize` returns `409`

## Acceptance Criteria
- Fresh install can be completed without manual DB edits.
- The instance can survive a restart and remain initialized.
- The clinic has a working admin account and a first branch.
- No separate setup state table was required.

## Evidence To Save
- Host name / release tag
- Initial and post-setup `setup/status` responses
- Login success proof
- `CURRENT_ORIGIN`, `RESOLVED_API_ORIGIN`, and `RESOLVED_WS_ORIGIN`
- Restart proof
- Any activation result if an activation key was used
