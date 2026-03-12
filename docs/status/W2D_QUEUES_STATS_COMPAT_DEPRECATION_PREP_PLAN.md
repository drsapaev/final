## W2D queues.stats compatibility deprecation-prep plan

## Scope

Bounded contract-prep slice for:

- [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py)
- [test_openapi_contract.py](C:/final/backend/tests/test_openapi_contract.py)
- docs/status for the compatibility-field tail

## Intended change

Keep `GET /api/v1/queues/stats` mounted and behaviorally unchanged, but make the
remaining legacy compatibility fields explicit in OpenAPI:

- `is_open`
- `start_number`

## Why this is the narrowest safe step

- no route removal
- no payload change
- no SSOT expansion
- no change to confirmed consumer-visible counters
- no contact with blocked `open_day` / `close_day` semantics

## What this should prove

- the route still owns strict counter behavior for live consumers
- the two legacy-only fields are now explicitly marked as compatibility fields
  on a retirement path
- the deprecation signal is machine-visible in OpenAPI

## Out of scope

- removing `is_open`
- removing `start_number`
- changing `queues.stats` consumers
- touching `next_ticket`
- broad OnlineDay refactor
