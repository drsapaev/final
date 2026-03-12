# W2D next execution unit after board_state queue wiring

## Decision

`A) board_state parity/comparison harness`

## Why this is the safest next step

The internal adapter now has both major sections wired enough to compare:

- `display_metadata`
- `queue_state`

But mounted replacement is still not safe yet because:

- compatibility fields are still legacy-only
- some metadata ownership remains unresolved
- the mounted route contract still mismatches the live UI call shape

That makes a parity/comparison harness the smallest evidence-building step
before any bounded route replacement discussion.

## Why not the larger alternatives

### Why not `B) narrow mounted board_state replacement slice`

Replacement is still too early because the adapter candidate has not yet been
validated end-to-end against legacy behavior and consumer expectations.

### Why not `C) one more board_state compatibility wiring slice`

The remaining compatibility fields are `is_open` and `start_number`, both tied
to the OnlineDay legacy island. A direct compatibility wiring slice is less
useful before proving how the already-wired adapter candidate behaves.

### Why not `D) human review needed`

Human review may still be needed later for unresolved metadata ownership, but it
is not required before building a bounded comparison harness.
