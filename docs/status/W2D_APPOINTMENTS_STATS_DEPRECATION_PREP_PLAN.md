## W2D appointments.stats deprecation-prep plan

## Scope

Bounded deprecation-prep slice for:

- [appointments.py](C:/final/backend/app/api/v1/endpoints/appointments.py)
- [test_openapi_contract.py](C:/final/backend/tests/test_openapi_contract.py)
- appointments.stats deprecation docs/status

## Intended code change

Apply explicit OpenAPI deprecation signaling to:

- `GET /api/v1/appointments/stats`

The route will remain:

- mounted
- readable
- behaviorally unchanged

## Why this is the narrowest safe fix

- no route removal
- no redirect
- no runtime payload change
- no new owner introduced
- no OnlineDay write/admin surface touched

## What this slice should prove

- the duplicate legacy status of `appointments.stats()` is explicit in the
  public contract
- OpenAPI now communicates that the route is on the retirement path
- runtime behavior stays unchanged

## Out of scope

- actual route retirement
- redirect to `queues.stats()`
- consumer migration/removal
- any change to `open_day`, `close_day`, `next_ticket`
