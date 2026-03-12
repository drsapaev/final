## W2D Next Execution Unit After queues.stats Compatibility Deprecation Prep

## Recommended next step

`return to legacy/deprecation review and pick the next bounded OnlineDay read tail`

## Why this is the safest next step

- the `queues.stats` compatibility tail is now contractually explicit
- the route still safely serves live counter consumers
- no additional bounded action on this exact route is higher-value than moving
  to the next remaining legacy read surface

## Suggested next candidate

- `board/state` remaining legacy fallback review, but only for the still-legacy
  compatibility dependency itself, not for product-blocked `is_paused` /
  `is_closed`

## Why not touch blocked admin surfaces

`open_day`, `close_day`, and `next_ticket` remain blocked by ops/external usage
or deprecate-later constraints.
