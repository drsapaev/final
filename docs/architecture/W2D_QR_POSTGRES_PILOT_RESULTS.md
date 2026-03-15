## Wave 2D QR Postgres Pilot Results

Date: 2026-03-11
Mode: pilot-extension, evidence-based

## Commands used

SQLite lane:

```powershell
cd backend
pytest tests/characterization/test_qr_queue_direct_sql_concurrency.py -q -c pytest.ini
```

Postgres lane:

```powershell
cd backend
pytest tests/characterization/test_qr_queue_direct_sql_concurrency.py -q -c pytest.ini --db-backend=postgres
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

The QR direct-SQL concurrency characterization stayed stable in both lanes:

- same-session replay still fails without creating an extra row
- two pending sessions still converge to a single queue entry

## Drift classification

This pilot family did not surface:

- true DB/schema drift
- harness/session issue
- new direct-SQL concurrency drift caused by the DB backend

The result is best classified as:

- no meaningful DB drift for this family in the current pilot harness

## What this means

- the pilot strategy now covers eight bounded queue-sensitive families
- the validated harness continues to provide honest signal in historically
  sensitive QR/direct-SQL territory
- we can keep extending one family at a time without broad fixture migration
