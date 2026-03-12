## Scope

Narrow metadata-extension slice for the new additive board-display endpoint:

- in scope:
  - `logo`
  - `contrast_default`
  - `kiosk_default`
- out of scope:
  - `is_paused`
  - `is_closed`
  - `queue_state`
  - websocket flow
  - legacy `/api/v1/board/state` behavior

## Field ownership

| Field | Current effective source | Confirmed backend owner | Safe to move now | Fallback still needed | Reason |
| --- | --- | --- | --- | --- | --- |
| `logo` | `DisplayBoardUnified.jsx` currently reads `source.logo || source.logo_url` from compatibility source/default path | Yes | Yes | Yes | Safe owner exists through `Setting(category="display_board", key="logo")`; clinic-level `logo_url` can remain a compatibility fallback if present |
| `contrast_default` | Compatibility/default path only | Yes | Yes | No | Explicit owner exists in `Setting(category="display_board", key="contrast_default")` and the field is already edited through Settings UI |
| `kiosk_default` | Compatibility/default path only | Yes | Yes | No | Explicit owner exists in `Setting(category="display_board", key="kiosk_default")` and the field is already edited through Settings UI |
| `is_paused` | Compatibility/default path only | No | No | Yes | No confirmed display-config or settings owner found; current semantics remain ambiguous |
| `is_closed` | Compatibility/default path only | No | No | Yes | No confirmed display-config or settings owner found; current semantics remain ambiguous |

## Safe implementation strategy

- Extend the additive board-display endpoint only for `logo`, `contrast_default`, `kiosk_default`
- Source those values from already-confirmed settings owners
- Keep `is_paused` and `is_closed` on compatibility fallback in `DisplayBoardUnified.jsx`
- Keep the mounted legacy `/api/v1/board/state` route unchanged

## Why this slice is safe

- It stays metadata-only
- It does not pull queue counters or websocket behavior into scope
- It does not require an in-place contract change on the legacy board route
- It preserves a simple rollback path because `DisplayBoardUnified.jsx` still keeps compatibility fallback for unresolved fields
