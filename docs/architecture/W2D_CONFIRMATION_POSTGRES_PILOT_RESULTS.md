## Wave 2D Confirmation Postgres Pilot Results

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Commands used

SQLite lane:

```powershell
cd backend
pytest tests/characterization/test_confirmation_split_flow_concurrency.py -q -c pytest.ini
```

Postgres lane:

```powershell
cd backend
pytest tests/characterization/test_confirmation_split_flow_concurrency.py -q -c pytest.ini --db-backend=postgres
```

OpenAPI verification:

```powershell
cd backend
pytest tests/test_openapi_contract.py -q
```

## Results

- SQLite lane: `2 passed`
- Postgres lane: `2 passed`
- OpenAPI verification: `10 passed`

## Observed drift

No SQLite-vs-Postgres drift was observed in this family.

The concurrency characterization stayed stable in both lanes:

- parallel confirmation validation still allows the same pending token at the
  read phase
- parallel pending-visit lookup still observes the same pending visit in both
  threads

## Drift classification

This pilot family did not surface:

- true DB/schema drift
- harness/session issue
- new concurrency behavior drift caused by the DB backend

The result is best classified as:

- no meaningful DB drift for this family in the current pilot harness

## What this means

- the pilot strategy now covers six bounded queue-sensitive families
- the validated harness continues to distinguish real DB drift from stable
  concurrency behavior
- we can keep extending one family at a time without broad fixture migration
