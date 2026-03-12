## Wave 2D Service Code Drift Fix

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

## Exact mismatch fixed

The Postgres QR characterization pilot previously failed while inserting
`Service` rows with runtime-legitimate `service_code` values longer than the
current model limit.

Before this slice:

- `Service.service_code` was declared as `String(10)`
- Postgres rejected values such as `W2C-QR-LAB-EXISTING`
- SQLite accepted the same values, masking the mismatch

Applied fix:

- widened `Service.service_code` from `String(10)` to `String(32)` in
  `backend/app/models/service.py`

## Intended ownership

`service_code` is not only a short static code like `K01`.

Current live/test/runtime evidence shows it is a bounded service identifier used
for:

- SSOT-style compact codes (`K01`, `L032`, `D_PROC01`)
- operational identifiers (`CONSULT`)
- department-derived codes (`cardiology_consult`)
- QR characterization/setup identifiers (`W2C-QR-LAB-EXISTING`)

It is also already treated as closely aligned with `Service.code`, which is
declared as `String(32)`.

## Why `32` is the narrowest honest fix

- it accepts the bounded legitimate values already present in live/test code
- it aligns with the existing `Service.code` width
- it aligns with admin-departments contracts that already allow
  `service_code` up to `32`
- it preserves uniqueness and indexing

## Validation added

Added:

- `backend/tests/unit/test_service_service_code_schema.py`

This guard test proves:

- the schema now exposes `service_code` as `String(32)`
- currently observed legitimate values fit inside the declared bound

## Postgres pilot impact

This fix removed the original Postgres blocker in the QR characterization
family.

After the fix, the Postgres lane progressed further and exposed the next honest
drift:

- a timezone-awareness / datetime round-trip mismatch on `queue_time`

That means the original `service_code` blocker is resolved cleanly, and the
pilot can now continue one blocker at a time without broad fixture churn.

## Out of scope

- broad service-domain redesign
- harmonizing every endpoint-level `service_code` validator
- QR flow behavior changes
- broader Postgres fixture migration
