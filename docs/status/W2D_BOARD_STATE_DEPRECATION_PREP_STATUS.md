# W2D board.state deprecation-prep status

## Slice verdict

`SUCCESS`

## Outcome

Legacy `/api/v1/board/state` is now explicitly marked as deprecated in OpenAPI
while remaining mounted and behaviorally unchanged.

## Why this matters

This makes the current architecture honest:

- the new board-display endpoint is the intended metadata path
- `/board/state` is now contractually visible as compatibility-only

## What remains unchanged

- `DisplayBoardUnified.jsx` still keeps the route as fallback
- `is_paused` / `is_closed` remain unresolved product-blocked semantics
- rollback safety remains intact

## Verification

OpenAPI contract checks passed after the change.
