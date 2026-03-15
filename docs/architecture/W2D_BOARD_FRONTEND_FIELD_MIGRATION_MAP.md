## Purpose

This document maps the fields currently consumed by the frontend from legacy `/board/state` to the new adapter-backed board-display endpoint:

- legacy route: `GET /api/v1/board/state`
- future route: `GET /api/v1/display/boards/{board_key}/state`

The mapping is focused on the current live consumer `frontend/src/pages/DisplayBoardUnified.jsx`.

## Clean Field Mapping

| Frontend need | Legacy source today | New endpoint source | Mapping status | Workaround needed |
| --- | --- | --- | --- | --- |
| `brand` | `st.brand` or `st.title` | `display_metadata.brand` | Clean | No |
| `announcement` | `st.announcement` or `st.ticker` | `display_metadata.announcement` | Clean | No |
| `announcement_ru` | `st.announcement_ru` | `display_metadata.announcement_ru` | Clean | No |
| `announcement_uz` | `st.announcement_uz` | `display_metadata.announcement_uz` | Clean | No |
| `announcement_en` | `st.announcement_en` | `display_metadata.announcement_en` | Clean | No |
| `primary_color` | `st.primary_color` | `display_metadata.primary_color` | Clean | No |
| `bg_color` | `st.bg_color` | `display_metadata.bg_color` | Clean | No |
| `text_color` | `st.text_color` | `display_metadata.text_color` | Clean | No |
| `sound_default` | `st.sound_default !== false` | `display_metadata.sound_default` | Clean | No |

## Fields Missing on the New Endpoint v1

| Frontend need | Legacy source today | New source | Missing | Workaround needed |
| --- | --- | --- | --- | --- |
| `logo` | `st.logo` or `st.logo_url` | None in v1 | Yes | Yes |
| `is_paused` | `st.is_paused` or `st.paused` | None in v1 | Yes | Yes |
| `is_closed` | `st.is_closed` or `st.closed` | None in v1 | Yes | Yes |
| `contrast_default` | `st.contrast_default` | None in v1 | Yes | Yes |
| `kiosk_default` | `st.kiosk_default` | None in v1 | Yes | Yes |

## Fields That Should Stay Outside This Migration

These are not blockers for the first metadata migration because they do not belong to the new metadata-only v1 endpoint:

| Concern | Current source | Why it stays separate |
| --- | --- | --- |
| Queue counters (`last_ticket`, `waiting`, `serving`, `done`) | `/queues/stats` | Already separated from board metadata in current UI |
| Queue windows / cabinet state | `/queue/queue/status` | Different concern and route owner |
| Current call / live entries / live announcements | `openDisplayBoardWS(boardId, ...)` | Realtime transport, not metadata endpoint |

## Consumer Notes

`DisplayBoardUnified.jsx` already has a stable `boardId` source:

- prop default `boardId = 'main_board'`
- runtime override from query param `?board=...`

That means `board_key` resolution is already available for the first staged frontend migration.

## Migration Interpretation

The cleanest first frontend move is:

- migrate only the fields that map cleanly to `display_metadata.*`
- keep unresolved fields on a temporary frontend fallback path
- avoid mixing queue counters or websocket state into the first metadata switch
