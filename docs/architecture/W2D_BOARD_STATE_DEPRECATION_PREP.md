# W2D board.state deprecation prep

## What changed

The mounted legacy route:

- `GET /api/v1/board/state`

is now explicitly marked as deprecated in OpenAPI.

The route remains:

- mounted
- readable
- behaviorally unchanged

## Why this is the right preparation step

The board page is already mostly off the legacy route for metadata.

What remained after the board fallback review was not another migration-sized
engineering gap. What remained was a compatibility surface that still helps
with:

- rollback safety
- fallback behavior while product-blocked flags stay unresolved

So the safest next move was to mark the route for deprecation rather than keep
pretending it is a normal long-term board API.

## What did not change

This slice intentionally did not:

- remove `/board/state`
- change the route payload
- move `is_paused` / `is_closed`
- change board queue-state behavior
- touch websocket flow

## Practical effect

The project now has a clearer contract split:

- new board-display metadata should come from
  `GET /api/v1/display/boards/{board_key}/state`
- legacy `/board/state` remains only as a compatibility/rollback route

That makes future retirement work more straightforward without forcing it now.
