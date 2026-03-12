## Wave 2D Force Majeure Postgres Pilot Results

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Commands used

SQLite lane:

```powershell
cd backend
pytest tests/characterization/test_force_majeure_allocator_characterization.py -q -c pytest.ini
```

Postgres lane:

```powershell
cd backend
pytest tests/characterization/test_force_majeure_allocator_characterization.py -q -c pytest.ini --db-backend=postgres
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

The exceptional-domain characterization stayed stable in both lanes:

- transfer still allocates a new number on the tomorrow queue
- duplicate gating still remains intentionally absent in the characterized path
- `force_majeure_transfer` source behavior remained the same

## Drift classification

This pilot family did not surface:

- true DB/schema drift
- harness/session issue
- new exceptional-domain behavior drift caused by DB backend

The result is best classified as:

- no meaningful DB drift for this family in the current pilot harness

## What this means

- the pilot strategy now covers five bounded queue-sensitive families
- Postgres sensitivity is real, but the current harness continues to separate
  real drift from stable legacy/exceptional behavior
- this strengthens confidence in the staged pilot approach without requiring a
  broad fixture migration
