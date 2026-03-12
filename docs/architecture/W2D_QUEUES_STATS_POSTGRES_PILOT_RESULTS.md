## Wave 2D Queues Stats Postgres Pilot Results

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Commands used

SQLite lane:

```powershell
cd backend
pytest tests/characterization/test_queues_stats_parity_harness.py -q -c pytest.ini
```

Postgres lane:

```powershell
cd backend
pytest tests/characterization/test_queues_stats_parity_harness.py -q -c pytest.ini --db-backend=postgres
```

OpenAPI verification:

```powershell
cd backend
pytest tests/test_openapi_contract.py -q
```

## Results

- SQLite lane: `3 passed`
- Postgres lane: `3 passed`
- OpenAPI verification: `10 passed`

## Observed drift

No SQLite-vs-Postgres drift was observed in this family.

The legacy-vs-SSOT parity behavior remained stable in both lanes:

- strict fields still matched as expected
- compatibility-only mismatches remained the same
- the family did not reveal new schema, transaction, or session-routing issues

## Drift classification

This pilot family did not surface:

- true DB/schema drift
- harness/session issue
- new parity-contract drift caused by the DB backend

The observed behavior is best classified as:

- no meaningful DB drift for this family in the current pilot harness

## What this means

- the dual-lane pilot now covers a third queue-sensitive family successfully
- Postgres alignment concerns are real, but not universal across all
  queue/legacy-sensitive families
- the pilot strategy continues to produce honest signal with very small blast
  radius
