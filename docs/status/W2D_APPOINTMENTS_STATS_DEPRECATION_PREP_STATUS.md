## Status

Completed.

## What changed

- `GET /api/v1/appointments/stats` is now explicitly marked as deprecated in
  OpenAPI
- route behavior remains unchanged
- a contract test now protects the deprecation signal

## Validation

- OpenAPI contract test passed
- no runtime route removal was performed

## Interpretation

This slice does not retire the route.

It simply moves `appointments.stats()` from:

- implicit duplicate legacy surface

to:

- explicit duplicate legacy surface on a retirement path
