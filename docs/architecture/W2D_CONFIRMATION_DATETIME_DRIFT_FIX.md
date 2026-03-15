## Wave 2D Confirmation Datetime Drift Fix

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

## Exact mismatch fixed

The aggregated Postgres `postgres_pilot` marker lane failed in the confirmation
family because the confirmation domain mixed:

- timezone-aware columns
- naive `datetime.utcnow()` writes and comparisons

Observed failure:

- `Visit.confirmation_expires_at` is declared as `DateTime(timezone=True)`
- the confirmation concurrency family wrote a naive
  `datetime.utcnow() + timedelta(hours=2)`
- SQLite kept the path effectively naive-shaped
- Postgres read the column back as an aware datetime
- the runtime then compared it against naive `datetime.utcnow()`
- Python raised:
  `can't compare offset-naive and offset-aware datetimes`

## Classification

This was a real runtime/domain drift exposed by Postgres, not just a test
expectation issue.

The underlying inconsistency was:

- confirmation-related runtime writers still produced naive datetimes
- confirmation-related runtime compare paths still used naive `datetime.utcnow()`

## Applied fix

Added a confirmation-local helper module:

- `backend/app/services/confirmation_datetime.py`

It provides:

- `confirmation_utc_now()`
- `normalize_confirmation_datetime(...)`
- `is_confirmation_expired(...)`

Then updated only confirmation-related paths to use it:

- `backend/app/services/confirmation_security.py`
- `backend/app/services/visit_confirmation_service.py`
- `backend/app/api/v1/endpoints/doctor_integration.py`
- `backend/app/services/doctor_integration_api_service.py`
- `backend/app/api/v1/endpoints/registrar_wizard.py`
- `backend/app/services/registrar_wizard_api_service.py`

Also aligned confirmation-family tests/fixtures that write
`confirmation_expires_at` so they now use aware UTC values.

## Why this is the narrowest honest fix

- it stays inside confirmation-related runtime and test code
- it avoids a global datetime refactor
- it fixes both write-time and compare-time drift for the same field family
- it does not weaken assertions or hide the underlying behavior difference

## Validation added

Added:

- `backend/tests/unit/test_confirmation_datetime.py`

This guard proves:

- naive confirmation datetimes are normalized as UTC
- expiry checks behave consistently for aware and naive inputs

## Postgres pilot impact

This fix removed the last remaining blocker in the aggregated
`postgres_pilot` marker lane.

After the fix:

- SQLite marker lane: `28 passed, 764 deselected`
- Postgres marker lane: `28 passed, 764 deselected`
- OpenAPI verification: `10 passed`

## Strategic implication

The marker-driven dual-lane pilot is now green in both DB lanes.

That moves the project out of “bounded drift cleanup” mode and into the next
safe step:

- dedicated CI wiring for `postgres_pilot`

## Out of scope

- global datetime normalization across the app
- non-confirmation datetime cleanup
- queue-domain redesign
- broad fixture migration
