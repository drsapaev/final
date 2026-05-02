# 2026-03-27 registrar all-appointments full_name

## Summary
- Registrar `all-appointments` search now works with the current `Patient` model and returns paid rows instead of failing on a missing `full_name` attribute.

## Root cause
- Multiple downstream flows still expected `Patient.full_name`, but the model only exposed `short_name()`.
- The search predicate inside `registrar/all-appointments` also needed a portable SQL expression so test DBs and Postgres both evaluate it consistently.

## Fix
- Added a `Patient.full_name` hybrid property that reuses the canonical patient name formatting.
- Kept the `registrar/all-appointments` search predicate portable with SQLAlchemy string concatenation and `coalesce`.

## Verification
- Integration regression passed: `backend/tests/integration/test_registrar_all_appointments.py`
- Live backend on `:18000` returned `200` for `GET /api/v1/registrar/all-appointments?search=QA Smoke BCDEFG`
- The same response included the paid visit `748` with `payment_status=paid`
