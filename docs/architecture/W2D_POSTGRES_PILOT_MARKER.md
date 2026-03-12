## Postgres Pilot Marker Layer

## What was added

A new `pytest` marker was introduced in [pytest.ini](C:/final/backend/pytest.ini):

- `postgres_pilot`

The marker is applied to the already validated bounded queue-sensitive pilot
families in `backend/tests/characterization/`.

## Why this is the right first operationalization step

- it creates a single source of truth for pilot families
- it avoids hand-maintaining long file lists in ad hoc commands
- it is smaller and safer than jumping straight to CI wiring
- it keeps the current SQLite default lane intact

## Current command surface

SQLite pilot lane:

```powershell
cd C:\final\backend
pytest -m postgres_pilot -q -c pytest.ini
```

Postgres pilot lane:

```powershell
cd C:\final\backend
pytest -m postgres_pilot -q -c pytest.ini --db-backend=postgres
```

## Outcome of the first aggregated marker run

SQLite marker lane:

- `28 passed, 761 deselected`

Postgres marker lane:

- `26 passed, 2 failed, 761 deselected`

The marker layer itself worked correctly and exposed the next honest drift in
the confirmation family.

## Newly surfaced blocker

The aggregated Postgres pilot run revealed a bounded schema drift in
[visit.py](C:/final/backend/app/models/visit.py):

- `Visit.status -> String(16)` is too short for the already used runtime value
  `pending_confirmation`

This is exactly the kind of issue the pilot is supposed to surface before broad
infra migration or CI rollout.

## Outcome after the narrow `Visit.status` fix

After the next bounded follow-up slice:

- SQLite marker lane: `28 passed, 762 deselected`
- Postgres marker lane: `27 passed, 1 failed, 762 deselected`

The marker layer still behaves correctly, and the lane progressed beyond the
old schema-length blocker.

## Newly surfaced blocker after that slice

The current remaining Postgres marker-lane blocker is now inside the same
confirmation family, but at a different layer:

- `confirmation_expires_at` comes back timezone-aware under Postgres
- the validation path still compares it against naive `datetime.utcnow()`
- this surfaces as `can't compare offset-naive and offset-aware datetimes`

That was no longer a marker-layer issue and no longer the old status-length
issue. It was the next honest blocker surfaced by the aggregated pilot run.

## Outcome after the confirmation datetime fix

After the next bounded follow-up slice:

- SQLite marker lane: `28 passed, 764 deselected`
- Postgres marker lane: `28 passed, 764 deselected`

The marker layer is now fully green in both DB backends.

## What this means

The marker layer is successful and operationally ready.

It now serves as the single source of truth for the dedicated CI guardrail job:

- family list is centralized in the marker
- the dual-lane pilot is validated
- the aggregated marker lane is green in both SQLite and Postgres
- CI can execute the same bounded lane without duplicating file lists

The CI follow-up is documented in
[W2D_POSTGRES_PILOT_CI.md](C:/final/docs/architecture/W2D_POSTGRES_PILOT_CI.md).
