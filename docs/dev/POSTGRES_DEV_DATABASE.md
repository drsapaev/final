# PostgreSQL Dev Database Workflow

This project is PostgreSQL-only for local manual UI testing. Do not switch the
backend runtime back to SQLite.

## Reset And Seed

Use a disposable local dev database such as `clinic_dev`.

If the database does not exist yet, create it with a PostgreSQL admin user and
make the app role the owner. Example with `psql`:

```powershell
psql -h localhost -U postgres -d postgres -c "CREATE DATABASE clinic_dev OWNER clinic;"
```

```powershell
cd C:\final\backend
$env:ENV="dev"
$env:DATABASE_URL="postgresql+psycopg://clinic:<dev_password>@localhost:5432/clinic_dev"

python -m app.scripts.reset_dev_db `
  --mode schema `
  --seed demo `
  --confirm-dev-reset `
  --confirm-dev-seed `
  --confirm-db-name clinic_dev
```

The command:

- refuses production environment markers from `ENV`, `APP_ENV`, or `ENVIRONMENT`
- refuses SQLite and non-PostgreSQL URLs
- refuses suspicious database names such as `prod`, `production`, `clinic_prod`, `live`, and `main`
- refuses remote hosts unless `--allow-remote-dev-db` is passed
- prints a preflight summary before destructive reset work
- resets the `public` schema by default
- runs `alembic upgrade head`
- optionally runs the demo seed

## Seed Only

Run this after migrations are already applied:

```powershell
cd C:\final\backend
$env:ENV="dev"
$env:DATABASE_URL="postgresql+psycopg://clinic:<dev_password>@localhost:5432/clinic_dev"

python -m app.scripts.dev_seed --profile demo --confirm-dev-seed
```

The demo seed is designed to be idempotent. Running it twice should update the
same demo users, patients, visits, queues, payments, EMR examples, lab reports,
and audit marker instead of creating duplicates.

## Local Demo Login

Admin and cashier are production-sensitive roles. If local auth requires 2FA for
those roles, use the existing dev/test override only for manual local UI smoke:

```powershell
$env:DISABLE_2FA_REQUIREMENT="1"
```

Do not use that flag in production-like environments.

## Non-Destructive Local Launch

For normal manual UI testing against `clinic_dev`, prefer the local launcher:

```powershell
cd C:\final
.\scripts\start_dev_clinic.ps1
```

The launcher:

- starts backend on `18000` and frontend on `5173`
- overrides `DATABASE_URL` only for the backend process, targeting `clinic_dev`
- does not edit `backend/.env`
- does not reset, seed, or migrate the database
- writes logs under `%TEMP%`
- prints/records PIDs in `%TEMP%\final-dev-clinic.pids.json`
- checks backend health and frontend proxy health

Use:

```powershell
.\scripts\check_dev_clinic.ps1
.\scripts\stop_dev_clinic.ps1
```

If ports are still occupied by processes not launched through the PID file, use
`.\scripts\stop_dev_clinic.ps1 -ForcePorts` only after confirming those
processes are the local dev clinic runtime.

## Recreate Database Mode

Use this only when the connected PostgreSQL role has enough privilege to drop and
create the target database.

```powershell
cd C:\final\backend
$env:ENV="dev"
$env:DATABASE_URL="postgresql+psycopg://clinic:<dev_password>@localhost:5432/clinic_dev"

python -m app.scripts.reset_dev_db `
  --mode recreate-db `
  --seed demo `
  --confirm-dev-reset `
  --confirm-dev-seed `
  --confirm-db-name clinic_dev
```

`--mode recreate-db` connects to the maintenance database, terminates active
connections to the target dev database, drops it, recreates it, and then runs
Alembic.

## Remote Disposable Dev DB

Remote databases are blocked by default. If a remote database is intentionally
disposable, add:

```powershell
--allow-remote-dev-db
```

Keep the database name explicit and non-production-like, for example
`clinic_dev_agent_01`.

## Safety Boundaries

- Seed/reset scripts are manual CLI tools only.
- The backend app startup does not import or run these scripts.
- Production setup behavior is unchanged.
- Demo credentials live only in the dev seed script and docs.
- Finalized EMR and lab data are created through existing service patterns, not by mutating finalized rows.
