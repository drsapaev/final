## Wave 2D Service Code Drift Fix Plan

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

## Exact mismatch

The Postgres QR characterization pilot surfaced a strict length mismatch during
`Base.metadata.create_all(...)` + family setup execution:

- `Service.service_code` is currently declared as `String(10)`
- the QR characterization family inserts legitimate current values such as
  `W2C-QR-LAB-EXISTING`
- Postgres rejects the insert because it enforces `VARCHAR(10)` strictly
- SQLite accepted the same setup value, which hid the mismatch

## Current model/runtime evidence

Current model declaration:

- `backend/app/models/service.py`
  - `service_code: mapped_column(String(10), nullable=True, unique=True, index=True)`

Live/runtime evidence that longer values are legitimate:

- `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`
  uses:
  - `W2C-QR-LAB-EXISTING`
  - `W2C-QR-LAB-NEW`
- `backend/app/api/v1/endpoints/admin_departments.py`
  and
  `backend/app/services/admin_departments_api_service.py`
  derive default service codes from:
  - `f"{department.key}_consult"`
- the admin-departments API contract already permits up to `max_length=32`
  for `service_code`
- `Service.code` is already declared as `String(32)`, and many paths treat
  `service_code` and `code` as interchangeable lookup identifiers

## Discovered legitimate source values

Confirmed current values include:

- short SSOT-style codes such as `K01`, `L032`, `D_PROC01`
- medium operational codes such as `CONSULT`
- QR/test/service setup codes such as `W2C-QR-LAB-EXISTING`
- department-derived codes such as `cardiology_consult`

## Max observed / current expected length

Observed bounded examples in current live/test code are below the existing
`Service.code` limit of `32`, but above the current `service_code` limit of
`10`.

This makes `32` the narrowest honest alignment target in this slice because it:

- accepts the currently observed legitimate values
- matches the existing `Service.code` ceiling
- matches the already-existing `max_length=32` admin-departments contract

## Chosen fix

Widen only the model-level `Service.service_code` column from `String(10)` to
`String(32)`.

Add a narrow schema guard test that proves:

- the column length now matches the intended bounded ownership
- known legitimate longer values fit

## Why this is the narrowest correct fix

- It fixes the exact Postgres-enforced mismatch that blocked the QR
  characterization family.
- It does not weaken integrity by removing uniqueness or indexing.
- It does not require enum redesign or broader service-domain refactoring.
- It keeps the one-drift-at-a-time pilot discipline intact.

## Explicitly out of scope

- broad service schema redesign
- endpoint-level validator harmonization across every service API surface
- queue/QR behavior changes
- broad fixture migration
- unrelated Postgres pilot families
