## Recommended Staged Strategy

The frontend migration should be staged, narrow, and reversible.

The safest sequence is:

1. Keep legacy `/board/state` unchanged.
2. Introduce a thin frontend adapter/service for the new board-display endpoint.
3. Move only `DisplayBoardUnified.jsx` to that adapter first.
4. Limit the first switch to metadata fields that already map cleanly.
5. Keep unresolved fields on local fallback/compatibility handling until they have confirmed owners.

Status update:

- Step 2 is now complete.
- Step 3 is now complete in a narrow staged form.
- `logo`, `contrast_default`, and `kiosk_default` are now also served by the
  new adapter-backed endpoint and consumed by `DisplayBoardUnified.jsx`.
- The remaining bounded frontend migration question is now limited to:
  - `is_paused`
  - `is_closed`

## Why `DisplayBoardUnified` Should Move First

`DisplayBoardUnified.jsx` is:

- the only confirmed live runtime consumer of `/board/state`
- already board-key aware
- already isolated from counters, queue-status, and websocket concerns

This makes it the smallest safe first frontend migration target.

## Recommended Frontend Shape

First migration should introduce:

- a dedicated frontend API wrapper or adapter for `GET /api/v1/display/boards/{board_key}/state`
- a small normalization layer that maps new `display_metadata` fields into the page's existing local board state
- compatibility fallback for unresolved fields:
  - `is_paused`
  - `is_closed`

## Dual-Read / Fallback Recommendation

Feature-flag style rollout is likely overkill for the first slice.

The simpler staged strategy is:

- use the new endpoint for confirmed metadata fields
- keep a local compatibility fallback path for unresolved fields
- leave counters on `/queues/stats`
- leave realtime updates on websocket
- leave windows/cabinets on `/queue/queue/status`

This keeps rollback simple because:

- backend legacy route remains untouched
- frontend can revert to the old metadata fetch path in one bounded change

## What Should Stay on Legacy Temporarily

During the first frontend switch, these should remain legacy/fallback driven:

- `is_paused`
- `is_closed`

Everything outside metadata should also remain on its current source:

- queue counters
- websocket-driven current call/entries
- queue-status/wait windows

## Not Recommended Yet

The following would be too large or too risky for the next slice:

- replacing multiple frontend consumers at once
- switching websocket or counter sources together with metadata
- replacing legacy `/board/state` in place
- bundling admin/config producer surfaces into the first migration

## Current staged state

Adapter-backed in `DisplayBoardUnified.jsx`:

- `brand`
- `logo`
- `announcement*`
- `primary_color`
- `bg_color`
- `text_color`
- `contrast_default`
- `kiosk_default`
- `sound_default`

Legacy compatibility only:

- `is_paused`
- `is_closed`

## Safest next bounded follow-up

Because the remaining legacy dependency is now limited to `is_paused` and
`is_closed`, the safest next step is a legacy-usage review for those exact
fields rather than another blind metadata extension.
