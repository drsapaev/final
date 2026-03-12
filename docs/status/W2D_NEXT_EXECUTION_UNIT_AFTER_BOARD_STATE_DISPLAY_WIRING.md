# W2D next execution unit after board_state display wiring

## Decision

`A) queue_state wiring prep/update`

## Why this is the safest next step

The adapter now has a real internal metadata surface, while mounted
`/board/state` still remains untouched. The next smallest bounded step is to
prepare or wire the queue-state side with the same discipline:

- keep it internal
- reuse the established SSOT queue-stats direction
- avoid mixing it into mounted route replacement yet

This is safer than a larger replacement because it keeps the work strictly
inside the adapter seams.

## Why not the alternatives

### Why not `B) announcement/config mapping follow-up`

Announcement input preparation is already sufficient for this stage. A deeper
announcement/config follow-up can happen later if mounted replacement proves it
necessary.

### Why not `C) board_state parity/comparison harness`

A parity harness becomes more useful after both metadata and queue-state inputs
exist inside the adapter. Right now a harness would still be comparing a
half-wired candidate.

### Why not `D) human review needed`

Human review is still relevant for unresolved fields like `logo` and
pause/closed semantics, but that does not block the next internal queue-state
prep slice.
