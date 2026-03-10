# W2D board_state target read adapter

## Target owner candidate

The safest future owner is not another allocator path and not the OnlineDay
service. It should be a dedicated read adapter, for example:

- `BoardStateReadAdapter`

This adapter should compose:

1. queue/read counters from SSOT read-models where needed
2. board/display metadata from display-config ownership
3. compatibility handling for fields that still lack a stable owner

## Recommended composition

### 1. Queue read source

Owner candidate:
- existing SSOT queue read-model direction already used for [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py)

Purpose:
- optional counter section if `board_state` keeps queue counters in its contract

Likely sources:
- `DailyQueue`
- `OnlineQueueEntry`
- department/day queue mapping logic

### 2. Display metadata source

Owner candidate:
- [display_config.py](C:/final/backend/app/models/display_config.py) models
- [crud/display_config.py](C:/final/backend/app/crud/display_config.py)

Relevant display-config data already exists for:
- board identity (`name`, `display_name`, `location`)
- sound defaults (`sound_enabled`)
- theme/colors (`colors`)
- announcement records (`DisplayAnnouncement`)

### 3. Compatibility layer

Still unresolved and likely needs explicit fallback or separate decision:
- `is_paused`
- `is_closed`
- multilingual board-level announcements
- `contrast_default`
- `kiosk_default`
- `logo` ownership

## Minimal first replacement target

For a first safe code step, the adapter should **not** replace the mounted route yet.
It should start as a skeleton that can produce:

- board identity / display metadata candidate
- config-derived defaults candidate
- optional counter composition hooks

without changing the public `GET /api/v1/board/state` behavior.

## Mapping assumptions

Likely mappings for a later route replacement:

- `brand`
  - from `DisplayBoard.display_name` or a clinic-brand owner
- `sound_default`
  - from `DisplayBoard.sound_enabled`
- `primary_color` / `bg_color` / `text_color`
  - from `DisplayBoard.colors`
- `announcement*`
  - from `DisplayAnnouncement` records or a later board-ticker adapter

But these mappings are not fully proven yet and should not be assumed as final
runtime truth until a dedicated adapter slice exists.

## Why this should be an adapter, not a direct replacement

`board_state` is a mixed surface:

- some future data can come from SSOT queue reads
- some future data belongs to display-config ownership
- some fields do not currently have a clean backend owner at all

That makes an adapter seam the safest bounded next step.
