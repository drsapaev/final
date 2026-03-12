# W2D OnlineDay Board/Stats Validation Plan

## Goal

Validate future SSOT-backed read surfaces against legacy OnlineDay read outputs
before replacing any live mounted endpoint.

## Comparison Strategy

### 1. Legacy Snapshot Baseline

Capture baseline outputs for:

- `GET /api/v1/queues/stats`
- `GET /api/v1/board/state`
- optionally `GET /api/v1/appointments/stats` for duplicate-surface parity

Use the same:

- department
- date
- operating day state

### 2. SSOT Candidate Comparison

For any future replacement candidate, compare:

- key presence
- numeric counters
- open/closed visibility semantics
- empty-state behavior
- error behavior for missing params or unsupported combinations

## Endpoint-Level Checks

### `queues.stats`

Need explicit checks for:

- `waiting`
- `serving`
- `done`
- `last_ticket`
- `is_open`
- date/department normalization behavior

### `board.state`

Need explicit checks for:

- counter parity versus legacy
- whether board visibility flags are preserved or intentionally redefined
- whether display configuration comes from the new owner correctly
- fallback behavior when optional board metadata is absent

### `appointments.stats`

Need parity check only if the endpoint is kept.
If the plan becomes redirect/retire, validation should instead prove the redirect path.

## Board Visibility Checks

Because the current board UI already mixes:

- `/queues/stats`
- `/board/state`
- local cache

validation must include:

- visible "now serving" block
- waiting list counts
- open/closed banner behavior
- no regression in default branding/announcement fallbacks

## Rollout / Rollback Notes

- First replacement slice should be read-only and dual-verifiable
- Keep legacy endpoint available until parity is confirmed
- If counts drift, rollback should be endpoint-level, not wave-wide

## Recommended Pre-Replacement Artifacts

- characterization snapshots for live department/day examples
- endpoint contract diff for `queues.stats`
- consumer mapping note for `DisplayBoardUnified`
- decision note for whether `appointments.stats` is retired or redirected
