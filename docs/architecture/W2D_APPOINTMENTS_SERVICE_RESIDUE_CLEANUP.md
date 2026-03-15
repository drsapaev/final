# W2D appointments service residue cleanup

## What changed

Removed:

- `backend/app/services/appointments_api_service.py`

Updated:

- `backend/tests/unit/test_service_repository_boundary.py`

## Why this was the correct cleanup

`appointments_api_service.py` no longer matched runtime truth.

The mounted appointments surface currently lives in:

- `backend/app/api/v1/endpoints/appointments.py`

and not through the removed service file.

The retained file had become misleading because it still bundled:

- old service logic
- duplicated router code

without being the actual runtime owner.

## What the boundary test change means

The service-boundary gate no longer pretends that the legacy appointments
surface has a live service-layer owner in `appointments_api_service.py`.

This is not a weakening of the currently active service/repository refactor
track. It is a correction of an outdated artifact expectation for a legacy
surface that is intentionally outside the main refactor path.

## What did not change

This slice did not:

- change `appointments.py` runtime behavior
- refactor appointments endpoints
- change OnlineDay semantics
- touch `open_day`, `close_day`, or `next_ticket`

## Architectural effect

The repository is now more honest:

- runtime appointments ownership stays where it actually is
- the support/test-only residue no longer suggests a fake service-layer owner
