# W2D Queues Stats Parity Plan

## Goal

Prepare evidence for replacing `GET /api/v1/queues/stats` without changing user-
visible behavior for the current board consumer.

## Legacy Snapshot Strategy

Before any route switch, capture legacy snapshots for representative cases:

1. active department/day with non-zero counters
2. active department/day with empty or near-empty counters
3. closed or inactive department/day if such a case exists in current data

Each snapshot should record:

- request params
  - `department`
  - `date`
- full legacy response
- if possible, the corresponding SSOT queue set used for comparison

## SSOT Comparison Fields

### Strict parity fields for first replacement

- `last_ticket`
- `waiting`
- `serving`
- `done`

### Compatibility-presence fields

- `department`
- `date_str`

These should remain present and normalized, even if they are not heavily used by
the current UI.

### Deferred / sign-off fields

- `is_open`
- `start_number`

These fields should not block initial prep, but they do block a blind full route
replacement unless one of these happens:

- temporary legacy fallback is retained
- explicit business sign-off allows a redefinition

## Endpoint-Level Regression Checks

Any future replacement slice should verify:

- same mounted path: `/api/v1/queues/stats`
- same required params: `department` and one of `d` / `date`
- same `422` behavior when date is missing
- same JSON key set unless compatibility reduction is explicitly approved

## Consumer-Level Validation

For `DisplayBoardUnified.jsx`, parity should confirm:

- "now serving" fallback still reflects `last_ticket`
- waiting / serving / done cards still render identical values
- cache fallback does not break on missing keys

## Acceptable Mismatch Categories

For the prep stage, acceptable mismatches are only analytical and must not reach
runtime yet.

Examples:

- SSOT candidate cannot yet reproduce `start_number`
- SSOT candidate needs a temporary compatibility source for `is_open`

Unacceptable for a live replacement:

- changed `last_ticket`
- drift in `waiting`, `serving`, or `done`
- missing required keys

## Rollout / Rollback Notes

Recommended first code step is dual-read validation, not route replacement:

- keep legacy endpoint as source of truth
- compute candidate SSOT projection in parallel
- diff the fields that matter

If parity fails:

- rollback is trivial because no route switch has happened yet
- the output becomes a focused gap list for the next slice
