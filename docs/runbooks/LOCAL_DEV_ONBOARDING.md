# Local Dev Onboarding (Postgres-First)

## Scope
- Local development setup for backend + frontend.
- PostgreSQL is the only source of truth for schema/data.
- SQLite `clinic.db` is not used for active development.

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

## 3. Start Services
Backend:
```powershell
cd c:\final\backend
uvicorn app.main:app --reload --port 8000
```

Frontend:
```powershell
cd c:\final\frontend
npm install
npm run dev
```

## 4. Validate Quality Gates Locally
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
- `docs/runbooks/POSTGRES_DR_RUNBOOK.md`
- `docs/runbooks/OBSERVABILITY_SLA_RUNBOOK.md`
- `docs/runbooks/LOAD_TESTING_RUNBOOK.md`
