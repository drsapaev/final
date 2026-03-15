# W2D board new endpoint response

## Mounted skeleton direction

The new endpoint is now mounted as a metadata-first, adapter-backed skeleton.

Current mounted top-level shape:

```json
{
  "board_key": "main_board",
  "display_metadata": {
    "brand": "Main Board",
    "logo": "/static/uploads/display/main-logo.png",
    "announcement": "Русское объявление",
    "announcement_ru": "Русское объявление",
    "announcement_uz": "O'zbekcha e'lon",
    "announcement_en": "English notice",
    "primary_color": "#0066cc",
    "bg_color": "#ffffff",
    "text_color": "#222222",
    "contrast_default": true,
    "kiosk_default": false,
    "sound_default": true
  }
}
```

`queue_state` is intentionally not mounted in v1.

Still deferred in the mounted contract:

- `is_paused`
- `is_closed`

## Field-level contract

### Top-level fields

| Field | Meaning | Source owner candidate | Required in v1 | Deferred |
| --- | --- | --- | --- | --- |
| `board_key` | Stable public board identifier | `DisplayBoard.name` | Yes | No |
| `display_metadata` | Metadata/config payload for the board UI | `BoardStateReadAdapter` composition | Yes | No |
| `queue_state` | Optional future queue summary section | SSOT queue read-model direction | No | Yes |

### `display_metadata`

| Field | Meaning | Source owner candidate | Required in v1 | Deferred |
| --- | --- | --- | --- | --- |
| `brand` | Board-facing clinic/board title | `DisplayBoard.display_name` or `name` | Yes | No |
| `announcement` | Default announcement text | `DisplayAnnouncement` adapter flattening | Yes | No |
| `announcement_ru` | Russian announcement | `DisplayAnnouncement` adapter flattening | Yes | No |
| `announcement_uz` | Uzbek announcement | `DisplayAnnouncement` adapter flattening | No | No |
| `announcement_en` | English announcement | `DisplayAnnouncement` adapter flattening | No | No |
| `primary_color` | Primary theme color | `DisplayBoard.colors.primary` | Yes | No |
| `bg_color` | Background color | `DisplayBoard.colors.background` | Yes | No |
| `text_color` | Text color | `DisplayBoard.colors.text` | Yes | No |
| `logo` | Logo URL/path for board header | `Setting(category="display_board", key="logo")` with clinic `logo_url` compatibility fallback | Yes | No |
| `contrast_default` | Default contrast mode for board UI | `Setting(category="display_board", key="contrast_default")` | Yes | No |
| `kiosk_default` | Default kiosk mode | `Setting(category="display_board", key="kiosk_default")` | Yes | No |
| `sound_default` | Default sound enabled flag | `DisplayBoard.sound_enabled` | Yes | No |
| `is_paused` | Pause mode indicator | unresolved operational/display owner | No | Yes |
| `is_closed` | Closed mode indicator | unresolved operational/display owner | No | Yes |

### Future `queue_state`

| Field | Meaning | Source owner candidate | Required in v1 | Deferred |
| --- | --- | --- | --- | --- |
| `department` | Department echo or mapped department | SSOT queue read-model direction | No | Yes |
| `date_str` | Queue-day echo | SSOT queue read-model direction | No | Yes |
| `last_ticket` | Latest issued ticket | SSOT counters | No | Yes |
| `waiting` | Waiting count | SSOT counters | No | Yes |
| `serving` | Serving count | SSOT counters | No | Yes |
| `done` | Completed count | SSOT counters | No | Yes |

## What should stay out of the public v1 contract

Legacy compatibility fields do not appear in the mounted v1 endpoint:

- `is_open`
- `start_number`

They remain OnlineDay compatibility concerns, not part of the public
board-display v1 contract.
