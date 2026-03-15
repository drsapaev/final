# W2D next execution unit after board_state wiring prep

## Decision

`A) wire display metadata sources only`

## Why this is the smallest safe next slice

This is the narrowest code step that creates real value without switching the
mounted route:

- the current live UI primarily needs board/display metadata
- confirmed backend sources already exist for a subset of metadata fields
- the adapter skeleton already has a clean `display_metadata` section
- queue counters are not the first missing piece for the current board page

That means we can safely wire confirmed metadata owners into the internal
adapter without touching:

- mounted `/board/state`
- `next_ticket`
- `open_day` / `close_day`
- broader display-domain contracts

## Why not the larger alternatives

### Why not `B) wire SSOT queue_state sources only`

`queue_state` is more prepared technically, but it is not the main consumer
problem:

- the live UI already reads counters from `/queues/stats`
- the current board page does not rely on `/board/state` for those counters

So queue-state-only wiring would not reduce the biggest replacement gap.

### Why not `C) build comparison/parity harness for adapter inputs`

A parity harness is more useful after at least some real metadata inputs are
wired. Right now the adapter would still have too many empty/unowned fields to
make a parity harness informative.

### Why not `D) human review needed before any wiring`

Human review is still needed later for unresolved fields such as:

- `is_paused`
- `is_closed`
- `logo`
- `contrast_default`
- `kiosk_default`

But that is not a blocker for wiring the already confirmed metadata subset.

## Proposed scope for the next slice

Wire only confirmed metadata owners into `BoardStateReadAdapter`:

- `brand`
- `primary_color`
- `bg_color`
- `text_color`
- `sound_default`

Potentially stage announcement source discovery next, but not in the same
slice unless it remains clearly bounded.
