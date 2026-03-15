## Postgres Pilot CI Plan

## Scope

This slice adds one dedicated CI job to the existing unified workflow:

- [ci-cd-unified.yml](C:/final/.github/workflows/ci-cd-unified.yml)

Related documentation updates:

- [W2D_POSTGRES_PILOT_CI.md](C:/final/docs/architecture/W2D_POSTGRES_PILOT_CI.md)
- [W2D_POSTGRES_PILOT_CI_STATUS.md](C:/final/docs/status/W2D_POSTGRES_PILOT_CI_STATUS.md)
- [W2D_POSTGRES_ALIGNMENT_REVIEW.md](C:/final/docs/architecture/W2D_POSTGRES_ALIGNMENT_REVIEW.md)
- [W2D_POSTGRES_PILOT_MARKER.md](C:/final/docs/architecture/W2D_POSTGRES_PILOT_MARKER.md)
- [W2D_POSTGRES_PILOT_MARKER_STATUS.md](C:/final/docs/status/W2D_POSTGRES_PILOT_MARKER_STATUS.md)

## Workflow target

The narrowest safe target is the existing unified workflow:

- [ci-cd-unified.yml](C:/final/.github/workflows/ci-cd-unified.yml)

Reason:

- it already owns the main backend guardrails
- it already provisions Postgres for backend-oriented jobs
- it already has `ci-scope`, so PR-only docs changes can keep skipping extra work

## Event scope

The new job should run for:

- pushes covered by the unified workflow
- pull requests covered by the unified workflow, but only when `ci-scope` says guardrails are required
- manual `workflow_dispatch`

The job should not run for the nightly `schedule` trigger in this slice.

## Exact command

From `backend/`:

```powershell
pytest -m postgres_pilot -q -c pytest.ini --db-backend=postgres
```

## Postgres service/config assumptions

Reuse the current backend CI conventions:

- `postgres:16`
- database: `clinicdb`
- user: `clinic`
- password: `clinicpwd`
- URL:
  `postgresql+psycopg://clinic:clinicpwd@localhost:5432/clinicdb`

The job should set both:

- `DATABASE_URL`
- `TEST_POSTGRES_DATABASE_URL`

This matches the current pilot harness lookup in
[conftest.py](C:/final/backend/tests/conftest.py).

## Why this is the narrowest safe CI slice

- no CI matrix expansion
- no replacement of existing SQLite/default jobs
- no broad pipeline redesign
- no migration of the whole suite to Postgres
- no change to application runtime behavior

## Explicitly out of scope

- nightly/deeper pilot scheduling
- broad CI modernization
- full Postgres test-stack migration
- pilot-family expansion in this slice
