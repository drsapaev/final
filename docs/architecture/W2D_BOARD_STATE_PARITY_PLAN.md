# W2D board_state parity plan

## Goal

Prove what should count as parity for `board_state` before any mounted route
replacement is attempted.

## Important constraint

This surface does not behave like `queues.stats`.

For `queues.stats`, strict counter parity was the main question.
For `board_state`, the main question is consumer-visible board metadata and
behavioral parity, not just field-by-field legacy counter parity.

## Legacy snapshot strategy

Capture evidence for:

1. mounted `GET /api/v1/board/state` response for representative department/day
2. actual `DisplayBoardUnified` behavior when `board_state` fails and falls back
3. current values coming from:
   - defaults in frontend
   - cached `board.state`
   - any separate display-config/admin data if present in environment

## Parity categories

### Strict parity candidates

Only if the future mounted route keeps them:
- `brand`
- `logo`
- `is_paused`
- `is_closed`
- visible announcement text
- key theme colors / sound default

### Compatibility/deferred categories

- `department`
- `date_str`
- legacy counter fields inside `board_state`
- exact legacy error details if the route later becomes less parameter-coupled

## Comparison strategy

For any future candidate adapter:

1. compare candidate output against current mounted response
2. compare candidate output against actual UI needs
3. explicitly separate:
   - legacy contract parity
   - consumer-visible parity

## Acceptable mismatch categories

Acceptable in prep/skeleton phases:
- internal adapter adds fields not yet mounted publicly
- candidate adapter omits legacy-only counters from its internal projection
- compatibility notes downgrade unverified fields instead of faking parity

Not acceptable for a mounted replacement:
- breaking visible board branding/theme behavior
- changing pause/closed banners unexpectedly
- dropping announcement behavior without an explicit replacement

## Rollout / rollback notes

- first code step should stay unmounted and internal
- mounted route should remain legacy-owned until adapter parity is characterized
- rollback should be route-local and not affect `queues.stats` or other OnlineDay surfaces

## Recommended pre-replacement artifacts

- board-state adapter skeleton
- consumer-usage-backed field map
- comparison note for `board_state` vs display-config sources
- explicit decision on whether counters remain part of future `board_state`
