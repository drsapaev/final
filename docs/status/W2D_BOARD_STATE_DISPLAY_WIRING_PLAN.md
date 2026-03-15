# W2D board_state display wiring plan

## Scope of this slice

This slice wires only confirmed or near-confirmed `display_metadata` sources
into the internal `BoardStateReadAdapter` without changing the mounted
`/board/state` runtime behavior.

## Fields to wire now

### Confirmed display-config owners

- `brand`
  - source: `DisplayBoard.display_name` with fallback to `DisplayBoard.name`
- `primary_color`
  - source: `DisplayBoard.colors["primary"]`
- `bg_color`
  - source: `DisplayBoard.colors["background"]`
- `text_color`
  - source: `DisplayBoard.colors["text"]`
- `sound_default`
  - source: `DisplayBoard.sound_enabled`

### Near-confirmed adapter-owned input preparation

- `announcement`
- `announcement_ru`
- `announcement_uz`
- `announcement_en`

These are allowed in this slice only as internal adapter input wiring over
`DisplayAnnouncement`-like records. No mounted route switch and no final
consumer contract claim will be made yet.

## Fields intentionally unresolved

The following remain placeholders in this slice:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

Reason:

- ownership is still unconfirmed or product semantics are unresolved

## Safety rationale

This slice is safe because:

- it does not switch mounted `/board/state`
- it does not change OpenAPI or frontend contracts
- it keeps `queue_state` untouched
- it only strengthens internal adapter composition for already identified
  display-domain sources

## In scope

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)
- unit tests for adapter-only wiring
- wiring/status docs

## Out of scope

- mounted `/board/state` replacement
- `queue_state` wiring
- `next_ticket`
- `open_day` / `close_day`
- broad display-domain refactor
