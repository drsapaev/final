# W2D next_ticket Validation Plan

## Purpose

Any future work on `next_ticket` needs validation against legacy behavior before replacement or retirement.

## Characterization needed

Minimum characterization cases:

1. missing `d/date` returns `422`
2. first ticket uses `start_number` offset correctly
3. repeated calls increment `ticket` monotonically
4. `waiting` increments on every call
5. `serving` and `done` remain unchanged
6. response shape stays `{ ticket, stats }`

## Parity checks needed

If a replacement candidate is introduced later, compare:

- returned `ticket`
- `stats.last_ticket`
- `stats.waiting`
- `stats.serving`
- `stats.done`
- `stats.is_open`
- `stats.start_number`

## Downstream regression checks

Also verify downstream legacy state remains coherent:

- `GET /api/v1/queues/stats`
- `GET /api/v1/board/state`
- legacy websocket `queue.update` payload shape if the route remains active

## Consumer validation

Before any retirement or mounted replacement:

- re-audit repo callers
- check external/manual usage assumptions with product or operations
- avoid assuming “no consumer” only from repo grep

## Rollout / rollback notes

Safest future rollout patterns:

- keep legacy route intact during comparison
- prefer additive harness or staged adapter first
- only remove or redirect after parity and ownership are proven

Rollback should remain simple:

- restore legacy route as source of truth
- avoid mixed semantics in one route during first replacement slice
