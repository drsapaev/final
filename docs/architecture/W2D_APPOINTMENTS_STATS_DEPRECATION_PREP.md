# W2D appointments.stats deprecation prep

## What changed

The mounted route:

- `GET /api/v1/appointments/stats`

now carries explicit OpenAPI deprecation signaling while remaining fully
mounted and behaviorally unchanged.

## Why this is the right bounded step

This route was already identified as:

- read-only
- duplicate of the same `load_stats(...)` contract behind `queues.stats()`
- lacking a confirmed in-repo live runtime consumer

That makes deprecation-prep a better fit than:

- immediate removal
- SSOT modernization
- redirect in the same slice

## What did not change

- no runtime payload change
- no route removal
- no redirect
- no OnlineDay write/admin behavior change
- no change to `open_day`, `close_day`, or `next_ticket`

## What the contract now communicates

The public API still exposes the route, but now signals that it is:

- legacy
- duplicate
- on a retirement path unless real consumers are confirmed

## Why this helps

It narrows the remaining OnlineDay surface in a low-risk way:

- consumers are warned at the contract level
- engineers no longer need to infer intent from scattered docs only
- future retirement can happen from a cleaner contract position
