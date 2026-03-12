## Postgres Pilot CI Guardrail

## What was added

A dedicated CI job now runs the validated Postgres pilot lane in:

- [ci-cd-unified.yml](C:/final/.github/workflows/ci-cd-unified.yml)

Job name:

- `🐘 Postgres Pilot`

## Exact command

From `backend/` the job runs:

```powershell
pytest -m postgres_pilot -q -c pytest.ini --db-backend=postgres
```

## Postgres service setup

The job provisions a dedicated Postgres service with the same narrow settings
already used elsewhere in unified CI:

- image: `postgres:16`
- database: `clinicdb`
- user: `clinic`
- password: `clinicpwd`
- port: `5432`

The job exports:

- `DATABASE_URL=postgresql+psycopg://clinic:clinicpwd@localhost:5432/clinicdb`
- `TEST_POSTGRES_DATABASE_URL=postgresql+psycopg://clinic:clinicpwd@localhost:5432/clinicdb`

This matches the current Postgres pilot harness lookup in
[conftest.py](C:/final/backend/tests/conftest.py).

## Trigger scope

The guardrail runs on:

- pushes covered by the unified workflow
- pull requests covered by the unified workflow when `ci-scope` says guardrails
  are required
- manual `workflow_dispatch`

It does **not** run on the nightly `schedule` trigger in this slice.

## What it protects

This job protects the already validated bounded `postgres_pilot` families:

- allocator characterization / concurrency
- open_day / close_day characterization
- queues.stats parity harness
- board_state parity harness
- force_majeure allocator characterization
- confirmation split-flow concurrency
- registrar batch allocator concurrency
- QR direct-SQL concurrency
- QR direct-SQL characterization

## Why SQLite remains the default baseline

SQLite still remains the default general-purpose test baseline because:

- it is faster
- the broad suite is already stable there
- the pilot work showed that a bounded Postgres lane is enough to surface real
  DB drift in the sensitive families without migrating everything immediately

## How this should evolve later

If new bounded queue-sensitive families are validated locally, they can be added
to the existing `postgres_pilot` marker. The CI job does not need redesign for
that; it will pick them up automatically through the shared marker.
