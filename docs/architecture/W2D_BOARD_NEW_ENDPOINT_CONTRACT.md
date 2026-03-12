# W2D board new endpoint contract

## Recommended endpoint

Recommended future public endpoint:

- `GET /api/v1/display/boards/{board_key}/state`

Where:

- `board_key` is a string identifier mapped to `DisplayBoard.name`
- example: `main_board`

## Why this path

This path is safer than reusing legacy `/board/state` because it:

- does not overload the OnlineDay legacy route
- clearly communicates that the resource is board-display specific
- aligns with the existing display-config domain naming
- avoids mixing queue semantics and display semantics under one legacy route

It should be treated as a board-display contract, not as a queue contract.

## HTTP method

- `GET`

This is a read-only surface.

## Request shape

### Required input

- `board_key` path param

### Not required in v1

- `department`
- `date`

Reason:

- the current live UI need for this surface is display metadata
- queue counters already come from other sources
- forcing `department/date` into the new board-display endpoint would recreate
  the legacy mismatch

### Optional future query params

If queue-state enrichment is added later, these may become optional query params:

- `department`
- `date`

But they should not be part of the first endpoint contract.

## Owner

Logical owner:

- `BoardStateReadAdapter`

Runtime owner candidate:

- a thin board-display API layer wrapping `BoardStateReadAdapter`

The route should remain a composition surface. It should not directly inherit
ownership from:

- OnlineDay legacy service
- queue allocator logic

## Why this is safer than `/board/state`

Legacy `/board/state` currently means:

- OnlineDay counter snapshot for a department/day

The new endpoint should mean:

- display-board state for a named board

These are different concepts. Different route surfaces make that explicit and
reduce rollout risk.

## Out-of-scope for v1

The new endpoint should not solve in its first version:

- `next_ticket`
- `open_day`
- `close_day`
- legacy OnlineDay compatibility retirement
- full queue-state consolidation
