# Wave 2C Next Execution Unit After Force Majeure Isolation

Date: 2026-03-09
Mode: analysis-first, docs-only

## Decision

`A) overall Wave 2C closure review`

## Why this is the best next step

- the main allocator-boundary track is effectively complete
- OnlineDay is isolated as a separate legacy island
- force_majeure is isolated as a separate exceptional-domain island
- what remains is mostly closure, cleanup prioritization, and side-track follow-up

## Why the other options were not chosen

### `B) dead/duplicate queue cleanup preparation`

Valuable, but better chosen after a closure review sets the exact cleanup scope.

### `C) narrow force_majeure correction slice`

Too early. The family is now isolated, but correction should follow a dedicated
exception-domain decision, not immediately after isolation.

### `D) human review needed`

Not needed for the isolation decision itself.
