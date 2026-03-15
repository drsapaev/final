# W2D board.state deprecation-prep plan

## Scope

This slice is limited to the legacy route:

- `GET /api/v1/board/state`

In scope:

- mark the route as deprecated in OpenAPI
- make the compatibility role explicit in code-facing contract metadata
- keep the route mounted and behaviorally unchanged
- add a narrow OpenAPI guard test

Out of scope:

- removing the route
- changing `DisplayBoardUnified.jsx` runtime behavior
- migrating `is_paused` / `is_closed`
- changing queue counters or websocket behavior

## Why this slice is safe

The route is already no longer the primary board metadata source.

This change only makes its current role explicit:

- compatibility fallback
- rollback path

No runtime payload or ownership semantics are changed.
