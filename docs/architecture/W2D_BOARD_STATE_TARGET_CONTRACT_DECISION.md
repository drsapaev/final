# W2D board_state target contract decision

## Recommended target direction

The recommended direction is an adapter-backed display-board contract exposed
through a new endpoint, while the current legacy `/board/state` route survives
during transition.

## Target owner

Target owner candidate:

- `BoardStateReadAdapter`
- later wrapped by a focused board-state API service or endpoint owner

The adapter should remain a composition owner, not a legacy OnlineDay owner and
not an allocator owner.

## Recommended public contract shape

The future adapter-backed contract should be metadata-first.

Recommended major sections:

- `display_metadata`
- `queue_state` (optional or additive in the first public version)

`compatibility` should remain an internal composition concern during transition,
not the main public story of the new endpoint.

## First-class fields

The following should be first-class in the future public contract because they
match the real UI need:

- `brand`
- `logo`
- `is_paused`
- `is_closed`
- `announcement`
- `announcement_ru`
- `announcement_uz`
- `announcement_en`
- `primary_color`
- `bg_color`
- `text_color`
- `contrast_default`
- `kiosk_default`
- `sound_default`

If `queue_state` is included, the initial safe set is:

- `department`
- `date_str`
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Deferred or compatibility-only concerns

These should not block the route-strategy decision:

- `is_open`
- `start_number`

They are legacy OnlineDay compatibility fields and should not drive the public
shape of the new board-display contract.

## Transition rule

During transition:

- keep `/board/state` unchanged as a legacy route
- add the new adapter-backed route separately
- migrate the frontend only after the new contract is explicit and testable

## Why this is the safest target contract

This shape aligns with actual UI needs and avoids forcing one route to serve two
different meanings:

- legacy counter snapshot
- display-board metadata contract

It also keeps future queue-state inclusion optional, instead of making counters
the center of a route the live UI already treats as display/config state.
