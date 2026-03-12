# W2D board legacy fallback review

## Scope

This pass re-checks the remaining runtime dependency on the legacy mounted route:

- `GET /api/v1/board/state`

The goal is to separate:

- remaining engineering dependency
- compatibility / rollback dependency
- product-blocked semantics

## Direct code-backed findings

### 1. The board page still calls the legacy route

The current live board page still fetches:

- new adapter-backed metadata via
  `fetchBoardDisplayStateV1(currentBoardId)`
- legacy compatibility data via
  `api.get('/board/state')`

Current direct runtime caller in the repo:

- `frontend/src/pages/DisplayBoardUnified.jsx`

No other confirmed frontend runtime caller was found in `frontend/src` outside:

- `DisplayBoardUnified.jsx`
- focused switch tests that intentionally assert the compatibility call remains

### 2. The legacy route does not own the blocked board flags

The mounted legacy route in `backend/app/api/v1/endpoints/board.py` returns only:

- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

It does **not** return:

- `is_paused`
- `is_closed`

So the remaining product-blocked board flags are not actually sourced from the
mounted legacy route.

### 3. The new board-display endpoint intentionally excludes those flags

The additive endpoint
`GET /api/v1/display/boards/{board_key}/state`
in `backend/app/api/v1/endpoints/board_display_state.py`
currently exposes only metadata-first board fields:

- `brand`
- `logo`
- `announcement*`
- `primary_color`
- `bg_color`
- `text_color`
- `contrast_default`
- `kiosk_default`
- `sound_default`

It also does **not** expose:

- `is_paused`
- `is_closed`

This is consistent with the current contract docs and with the frontend adapter
normalizer in `frontend/src/api/boardDisplay.js`, whose tests explicitly verify
that those fields are not part of the v1 metadata contract.

### 4. The remaining board-page dependency is now mostly compatibility / rollback

`DisplayBoardUnified.jsx` builds board state by preferring migrated metadata from
the new endpoint and reading the compatibility source only for fallback and
unresolved fields.

For the migrated fields, the legacy route is no longer the active owner:

- `brand`
- `logo`
- `announcement*`
- `primary_color`
- `bg_color`
- `text_color`
- `contrast_default`
- `kiosk_default`
- `sound_default`

What remains on the compatibility path:

- `is_paused`
- `is_closed`

But because the mounted legacy route does not return those flags, the effective
runtime source for them is currently limited to:

- cached compatibility payloads
- test/mocked payloads
- rollback-only legacy behavior when adapter-backed fetch is unavailable

### 5. The legacy route still has real value as a rollback path

Even though the board page is now mostly off the legacy route for metadata, the
page still keeps `/board/state` as:

- a compatibility fallback path when the adapter-backed request fails
- a legacy snapshot source for already-cached board state
- a low-risk rollback path while blocked semantics remain unresolved

That means the route is no longer the main board-state owner, but it is still a
live compatibility surface.

## What this means architecturally

The remaining board tail is now narrower than the route name suggests.

The unresolved work is **not**:

- more metadata migration
- more queue-state migration
- more adapter wiring

The unresolved work is:

- product/ownership clarification for `is_paused`
- product/ownership clarification for `is_closed`
- deciding when rollback compatibility can be removed

## Review conclusion

The remaining `/board/state` dependency is now mostly:

- compatibility fallback
- rollback safety

It is **not** the real current owner of the still-blocked board flags.

So the next engineering move should not be another speculative board-state
implementation slice. The correct next move is to treat `/board/state` as a
legacy compatibility surface and prepare it for deprecation without removing it
yet.
