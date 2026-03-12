# Wave 2C Next Macro Step

Date: 2026-03-09
Mode: analysis-first, docs-only

## Decision

`B) OnlineDay cleanup/deprecation preparation`

## Why this is the best next macro-step

- Wave 2C main allocator track is complete.
- OnlineDay still has a live mounted legacy surface.
- Unlike force_majeure, OnlineDay is not an intentional long-term exceptional
  queue domain; it is a legacy compatibility island.
- Preparing its cleanup/deprecation is the clearest next architectural step
  after closing Wave 2C.

## Why the other options were not chosen

### `A) Wave 2D payment / billing domain track`

Not chosen because Wave 2C just closed and the queue-specific legacy follow-up
is more immediately connected to the work already completed. Also, this review
must not auto-start Wave 2D.

### `C) force_majeure correction track`

Not chosen because force_majeure is an intentional exceptional-domain and does
not look as urgent as the still-mounted OnlineDay legacy surface.

### `D) dead/duplicate queue cleanup preparation`

Useful, but less important than defining the cleanup/deprecation plan for the
last live legacy queue island.

### `E) overall architecture/docs consolidation`

Partially achieved by this closure review already; better treated as supporting
work around later execution, not the primary next macro-step.
