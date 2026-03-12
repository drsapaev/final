## Decision

Chosen next step:

`A) extend board endpoint/frontend for unresolved metadata fields`

## Why This Is the Safest Next Step

The main staged contract switch has already happened for the clean metadata fields.

What remains is narrow and explicit:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

Extending the board endpoint/frontend for those fields is safer than moving immediately into broader legacy-route reduction, because it closes the known metadata gap first.

## Why Not Choose the Other Options

### Not `B) board_state legacy usage reduction review`

That review will be more meaningful after the unresolved metadata gap is either closed or intentionally frozen as compatibility-only.

### Not `C) next_ticket replacement prep`

`next_ticket` belongs to a different OnlineDay live surface and is outside the current board-display migration thread.

### Not `D) human review needed`

There is no new architectural blocker for the next narrow step. The remaining work is implementation-sized.

## Recommended Next Scope

The next slice should stay narrow:

- extend only the metadata shape needed for the unresolved board fields
- keep legacy `/board/state` untouched
- avoid pulling queue_state or websocket concerns into the same change
