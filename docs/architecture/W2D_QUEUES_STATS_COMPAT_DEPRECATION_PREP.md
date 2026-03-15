# W2D queues.stats compatibility deprecation prep

## What changed

`GET /api/v1/queues/stats` now has an explicit response model in OpenAPI, and
the remaining legacy compatibility fields are marked as deprecated:

- `is_open`
- `start_number`

## What did not change

- mounted route path stayed the same
- response payload keys stayed the same
- strict counter behavior stayed the same
- consumer-visible fields still remain:
  - `last_ticket`
  - `waiting`
  - `serving`
  - `done`

## Why this is the right bounded step

The route itself is still needed because confirmed live consumers still use the
strict counters.

But current evidence also shows:

- `is_open` is not a confirmed live consumer requirement
- `start_number` is not a confirmed live consumer requirement
- both fields remain tied to the OnlineDay legacy island

That makes field-level deprecation-prep a better move than route-level
deprecation.

## Why this helps

This makes the contract honest:

- strict counters remain first-class
- compatibility-only fields are explicitly shown as legacy

That gives a cleaner path for later removal of the compatibility tail without
confusing the route's still-live counter role.
