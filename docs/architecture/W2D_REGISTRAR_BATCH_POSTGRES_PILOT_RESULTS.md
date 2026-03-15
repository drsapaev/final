## Wave 2D Registrar Batch Postgres Pilot Results

Date: 2026-03-11
Mode: pilot-extension, evidence-based

## Commands used

SQLite lane:

```powershell
cd backend
pytest tests/characterization/test_registrar_batch_allocator_concurrency.py -q -c pytest.ini
```

Postgres lane:

```powershell
cd backend
pytest tests/characterization/test_registrar_batch_allocator_concurrency.py -q -c pytest.ini --db-backend=postgres
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

The registrar-batch concurrency characterization stayed stable in both lanes:

- repeated/parallel duplicate-read behavior remained the same
- no new transaction-visibility or identity-lifecycle divergence surfaced

## Drift classification

This pilot family did not surface:

- true DB/schema drift
- harness/session issue
- new concurrency behavior drift caused by the DB backend

The result is best classified as:

- no meaningful DB drift for this family in the current pilot harness

## What this means

- the pilot strategy now covers seven bounded queue-sensitive families
- the validated harness continues to provide honest signal with low migration
  risk
- we can keep extending one family at a time without broad fixture migration
