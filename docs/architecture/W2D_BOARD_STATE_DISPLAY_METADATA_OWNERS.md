# W2D board_state display metadata owners

## Summary

`board_state` replacement is blocked primarily by metadata ownership, not by queue
counters. The live UI in
[DisplayBoardUnified.jsx](C:/final/frontend/src/pages/DisplayBoardUnified.jsx)
mainly expects display/board metadata, while the mounted legacy route still
returns OnlineDay counters only.

The future `BoardStateReadAdapter` should therefore wire `display_metadata`
from existing display-config and clinic-branding sources first, instead of
starting from queue-state inputs.

## Field owner map

| Field | Current owner / candidate | Confirmed or assumed | Live source available | Replacement-ready |
| --- | --- | --- | --- | --- |
| `brand` | `DisplayBoard.display_name` with fallback to `DisplayBoard.name` in [display_config.py](C:/final/backend/app/models/display_config.py) and [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py) | Confirmed candidate | Yes | Yes |
| `logo` | Clinic branding asset, most likely uploaded via [admin_clinic.py](C:/final/backend/app/api/v1/endpoints/admin_clinic.py) `/clinic/logo`; no board-specific reader confirmed | Assumed candidate | Partial | No |
| `is_paused` | No confirmed backend owner found in current repo search | Missing owner | No | No |
| `is_closed` | No confirmed backend owner found in current repo search | Missing owner | No | No |
| `announcement` | Flattened adapter field over `DisplayAnnouncement.message` records in [display_config.py](C:/final/backend/app/models/display_config.py) | Confirmed candidate, adapter needed | Yes | Partial |
| `announcement_ru` | Language-specific projection over `DisplayAnnouncement` | Assumed candidate | Partial | No |
| `announcement_uz` | Language-specific projection over `DisplayAnnouncement` | Assumed candidate | Partial | No |
| `announcement_en` | Language-specific projection over `DisplayAnnouncement` | Assumed candidate | Partial | No |
| `primary_color` | `DisplayBoard.colors["primary"]` in [display_config.py](C:/final/backend/app/models/display_config.py) | Confirmed | Yes | Yes |
| `bg_color` | `DisplayBoard.colors["background"]` | Confirmed | Yes | Yes |
| `text_color` | `DisplayBoard.colors["text"]` | Confirmed | Yes | Yes |
| `contrast_default` | No confirmed backend owner found | Missing owner | No | No |
| `kiosk_default` | No confirmed backend owner found | Missing owner | No | No |
| `sound_default` | `DisplayBoard.sound_enabled` in [display_config.py](C:/final/backend/app/models/display_config.py) | Confirmed | Yes | Yes |

## Confirmed backend ownership

The following metadata sources are already present and usable as future adapter
inputs:

- `DisplayBoard.display_name` / `name` for board identity / brand-like label
- `DisplayBoard.colors` for `primary_color`, `bg_color`, `text_color`
- `DisplayBoard.sound_enabled` for `sound_default`
- `DisplayAnnouncement` rows for announcement content, but only after a
  flattening/selection adapter is introduced

These sources are read through:

- [crud/display_config.py](C:/final/backend/app/crud/display_config.py)
- [display_websocket.py](C:/final/backend/app/api/v1/endpoints/display_websocket.py)
- [display_websocket.py](C:/final/backend/app/services/display_websocket.py)

## Unresolved metadata owners

The following fields still lack a proven backend owner:

- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

`logo` also remains unresolved as a board-state field. The repo has a clinic
logo upload path, but no confirmed board-state read owner yet:

- [admin_clinic.py](C:/final/backend/app/api/v1/endpoints/admin_clinic.py)

This means `logo` is not blocked by missing storage, but by missing confirmed
read ownership and adapter semantics.

## Wiring implication

The safest first wiring slice should target only the metadata fields with
confirmed sources:

- `brand`
- `primary_color`
- `bg_color`
- `text_color`
- `sound_default`

Announcements are a likely second metadata step, because they require a
selection/flattening policy rather than simple field reads.

## Current slice status

The internal adapter now wires the following metadata fields:

- `brand`
- `primary_color`
- `bg_color`
- `text_color`
- `sound_default`
- `announcement`
- `announcement_ru`
- `announcement_uz`
- `announcement_en`

Implementation evidence:

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)
- [test_board_state_display_wiring.py](C:/final/backend/tests/unit/test_board_state_display_wiring.py)

The announcement fields are now adapter-owned input preparation, not a final
mounted runtime contract. They still depend on a later decision about record
selection/flattening semantics before route replacement.
