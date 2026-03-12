# W2D board new endpoint v1

## Smallest useful first version

The smallest useful first version should be:

- metadata-first
- board-key driven
- independent from OnlineDay request semantics

## Exact fields sufficient for first UI migration

### Required in v1

- `board_key`
- `display_metadata.brand`
- `display_metadata.announcement`
- `display_metadata.announcement_ru`
- `display_metadata.announcement_uz`
- `display_metadata.announcement_en`
- `display_metadata.primary_color`
- `display_metadata.bg_color`
- `display_metadata.text_color`
- `display_metadata.sound_default`

These are the fields with the clearest confirmed owners and the strongest
alignment with what the live UI already tries to consume.

## What may remain deferred in v1

Still deferred:

- `display_metadata.logo`
- `display_metadata.is_paused`
- `display_metadata.is_closed`
- `display_metadata.contrast_default`
- `display_metadata.kiosk_default`
- whole `queue_state` section

## Why `queue_state` should stay out of v1

For the first migration step:

- the live UI already gets counters elsewhere
- queue-state inclusion increases contract size without solving the primary
  mismatch
- leaving `queue_state` for a later additive step keeps the new endpoint narrow

## What remains unresolved or needs later decision

Business or ownership decisions still needed:

- who owns pause/closed state
- who owns logo delivery for board pages
- who owns contrast/kiosk defaults
- whether board-display contract should ever include counters directly

## V1 conclusion

V1 should be a board-display metadata endpoint, not a full "everything the board
page ever needs" endpoint.
