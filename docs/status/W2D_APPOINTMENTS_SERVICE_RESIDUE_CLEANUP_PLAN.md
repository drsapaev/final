# W2D appointments service residue cleanup plan

## Exact residue under review

- `backend/app/services/appointments_api_service.py`

## Why this is now in scope

Current runtime appointments ownership lives in:

- `backend/app/api/v1/endpoints/appointments.py`

The repository-wide search found no direct runtime imports of
`appointments_api_service.py`.

What still kept the file in place was:

- `backend/tests/unit/test_service_repository_boundary.py`

That test reads the file by path as an architecture artifact.

## Why cleanup is the honest move now

This file no longer reflects runtime truth:

- the mounted appointments route does not use it
- the file still contains a duplicated router block
- keeping it suggests a service-layer owner that runtime no longer has

That makes it residue, not a real compatibility surface.

## Intended narrow fix

1. remove the stale `appointments_api_service.py` residue
2. update the service-boundary gate so it no longer expects a non-runtime
   artifact for the legacy appointments surface
3. keep all runtime endpoints unchanged

## Out of scope

- refactoring `appointments.py` into service/repository style
- changing OnlineDay behavior
- changing mounted appointments routes
- touching blocked operational endpoints
