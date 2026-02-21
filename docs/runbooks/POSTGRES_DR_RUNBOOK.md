# Postgres DR Runbook (Dev)

## Scope
- Local development database `clinicdb` on PostgreSQL.
- SQLite `clinic.db` is out of scope and must not be changed.

## Preconditions
- PostgreSQL is running and reachable.
- `alembic` is available in `backend` environment.
- Application user credentials (read/write to target DB).
- Admin user credentials with `CREATEDB` privilege.

## Automated Procedure
Use the script:

```powershell
powershell -ExecutionPolicy Bypass -File ops/scripts/postgres_dr_test.ps1 `
  -PgHost localhost `
  -Port 5432 `
  -AppUser clinic `
  -AppPassword "<APP_PASSWORD>" `
  -AdminUser postgres `
  -AdminPassword "<ADMIN_PASSWORD>" `
  -Database clinicdb `
  -BackupDir "c:\final\backups\postgres" `
  -BackendDir "c:\final\backend"
```

What it does:
1. `pg_dump` backup to `*.dump`.
2. Terminates active DB sessions.
3. Drops and recreates `clinicdb`.
4. Runs `alembic upgrade head`.
5. Verifies `alembic current` equals head.

## Manual Procedure
1. Backup:
```powershell
$env:PGPASSWORD="<APP_PASSWORD>"
"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" -h localhost -p 5432 -U clinic -d clinicdb -F c -f c:\final\backups\postgres\clinicdb_manual.dump
```
2. Drop/recreate (admin user):
```powershell
$env:PGPASSWORD="<ADMIN_PASSWORD>"
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -w -h localhost -p 5432 -U postgres -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='clinicdb' AND pid<>pg_backend_pid();"
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -w -h localhost -p 5432 -U postgres -d postgres -c "DROP DATABASE IF EXISTS clinicdb;"
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -w -h localhost -p 5432 -U postgres -d postgres -c "CREATE DATABASE clinicdb OWNER clinic;"
```
3. Alembic migrate:
```powershell
cd backend
$env:DATABASE_URL="postgresql+psycopg://clinic:<APP_PASSWORD>@localhost:5432/clinicdb"
alembic upgrade head
alembic current
```

Expected result:
- `alembic current` prints `0001_baseline (head)`.

## Validation Log
- Validated on local environment: `2026-02-12`.
- Backup artifact example: `c:\final\backups\postgres\clinicdb_20260212_082534.dump`.
