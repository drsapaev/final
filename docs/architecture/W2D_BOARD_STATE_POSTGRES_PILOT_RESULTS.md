## Wave 2D Board State Postgres Pilot Results

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Commands used

SQLite lane:

```powershell
cd backend
pytest tests/characterization/test_board_state_parity_harness.py -q -c pytest.ini
```

Postgres lane:

```powershell
cd backend
pytest tests/characterization/test_board_state_parity_harness.py -q -c pytest.ini --db-backend=postgres
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

The legacy-vs-adapter parity behavior remained stable in both lanes:

- queue-state parity stayed intact
- compatibility-field parity stayed intact
- unresolved display-contract gaps remained the same contract-level issue, not a
  DB-lane issue

## Drift classification

This pilot family did not surface:

- true DB/schema drift
- harness/session issue
- new parity/adapter-contract drift caused by the DB backend

The result is best classified as:

- no meaningful DB drift for this family in the current pilot harness

## What this means

- the pilot strategy now covers four queue-sensitive families successfully
- DB-lane sensitivity is real, but it is clearly not universal across the whole
  queue/legacy tail
- the harness continues to provide honest signal with a small blast radius
