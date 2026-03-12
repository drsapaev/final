## Wave 2D QR Characterization Postgres Pilot Results

Date: 2026-03-11
Mode: pilot-extension, evidence-based

## Commands used

SQLite lane:

```powershell
cd backend
pytest tests/characterization/test_qr_queue_direct_sql_characterization.py -q -c pytest.ini
```

Postgres lane:

```powershell
cd backend
pytest tests/characterization/test_qr_queue_direct_sql_characterization.py -q -c pytest.ini --db-backend=postgres
```

OpenAPI verification:

```powershell
cd backend
pytest tests/test_openapi_contract.py -q
```

## Results

- SQLite lane: `4 passed`
- Postgres lane: `3 passed, 1 failed`
- OpenAPI verification: `10 passed`

## Observed drift

SQLite accepted the full QR characterization family.

Postgres surfaced one bounded failure in:

- `test_qr_direct_sql_characterization_full_update_first_fill_uses_raw_next_number_and_current_time`

The failure occurred before the QR assertions themselves completed.
Postgres rejected an insert into `services.service_code` because the test helper
currently sets:

- `code="W2C-QR-LAB-EXISTING"`
- `service_code=code`

while the model still declares:

- `Service.service_code -> String(10)`

The failing value is longer than the declared constraint, and SQLite did not
enforce that length in the same way.

## Drift classification

This slice surfaced:

- a real DB/schema drift in the QR characterization family

It did not surface:

- a harness/session issue
- a new QR queue concurrency issue

This is best classified as:

- `true DB/schema drift`, specifically around `Service.service_code` length
  enforcement under Postgres

## What this means

- the pilot strategy remains validated
- the QR characterization family is useful precisely because it exposed a real,
  bounded schema/test-data mismatch
- the safest next step is not broad fixture work, but a narrow follow-up on the
  `Service.service_code` length/ownership drift that this family uncovered
