## Status

Completed.

## What changed

- `GET /api/v1/queues/stats` now uses an explicit response model for OpenAPI
- `is_open` is marked deprecated
- `start_number` is marked deprecated
- strict counter fields remain non-deprecated

## Validation

- OpenAPI contract tests passed
- deprecation markers are now visible at the schema/property level

## Interpretation

This slice does not retire the fields yet.

It prepares the compatibility tail for future removal while preserving the live
counter contract that current consumers actually use.
