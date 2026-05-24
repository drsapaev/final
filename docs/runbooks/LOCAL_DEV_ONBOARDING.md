# Local Dev Onboarding (Postgres-First)

## Scope
- Local development setup for backend + frontend.
- PostgreSQL is the only source of truth for schema/data.

## Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 17+

## 1. Configure Backend
```powershell
cd c:\final\backend
python -m pip install -r requirements.txt
```

Create/update `backend/.env`:
```env
DATABASE_URL=postgresql+psycopg://clinic:<password>@localhost:5432/clinicdb
```

## 2. Apply Migrations
```powershell
cd c:\final\backend
alembic upgrade head
alembic current
```

Expected:
- `alembic current` points to head revision.

## 3. Reset And Seed A Disposable Dev DB
For manual UI testing, use a local disposable PostgreSQL database such as
`clinic_dev`:

```powershell
cd C:\final\backend
$env:ENV="dev"
$env:DATABASE_URL="postgresql+psycopg://clinic:<dev_password>@localhost:5432/clinic_dev"
$env:DISABLE_2FA_REQUIREMENT="1"

python -m app.scripts.reset_dev_db `
  --mode schema `
  --seed demo `
  --confirm-dev-reset `
  --confirm-dev-seed `
  --confirm-db-name clinic_dev
```

Seed-only rerun:

```powershell
python -m app.scripts.dev_seed --profile demo --confirm-dev-seed
```

See `docs/dev/POSTGRES_DEV_DATABASE.md` and `docs/dev/DEMO_USERS.md`.

## 4. Start Services
Backend:
```powershell
cd c:\final\backend
python run_server.py
```

Frontend:
```powershell
cd c:\final\frontend
npm install
npm run dev
```

## 5. Validate Quality Gates Locally
Backend contracts:
```powershell
cd c:\final\backend
pytest tests/test_openapi_contract.py -q
```

Frontend accessibility/UX checks:
```powershell
cd c:\final\frontend
npm run test:run -- src/pages/__tests__/Login.accessibility.test.jsx src/pages/__tests__/QueueJoin.accessibility.test.jsx src/test/accessibility/keyFlowContrast.test.js
```

## Related Runbooks
- `docs/dev/POSTGRES_DEV_DATABASE.md`
- `docs/dev/DEMO_USERS.md`
- `docs/runbooks/POSTGRES_DR_RUNBOOK.md`
- `docs/runbooks/OBSERVABILITY_SLA_RUNBOOK.md`
- `docs/runbooks/LOAD_TESTING_RUNBOOK.md`
