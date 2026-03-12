# Wave 2D Next Execution Unit After OnlineDay Prep

Date: 2026-03-09
Mode: analysis-first, docs-only

## Decision

`A) dead/disabled OnlineDay cleanup slice`

## Why this is the safest next step

- The OnlineDay legacy island is already isolated from the main queue track.
- Dead/disabled legacy surfaces have the lowest runtime risk.
- Removing dead/disabled pieces first reduces accidental future reuse without
  touching live mounted behavior.
- Support-only mirrors still need import/use verification.
- Live mounted endpoints still require replacement-prep and characterization
  before cleanup.

## Why the other options were not chosen

### `B) live mounted endpoint replacement prep`

This will still be needed, but it is not the narrowest safe next execution
unit. Dead/disabled cleanup is lower risk and simplifies later work.

### `C) support-only mirror cleanup slice`

Likely safe later, but still requires slightly more import/use verification than
the dead/disabled slice.

### `D) human review needed before cleanup`

Not required yet. The dead/disabled slice is clear enough to proceed without a
new business decision.

## Execution-unit verdict

The next safe step after this preparation pass is a narrow cleanup PR for:

- disabled OnlineDay routers
- dead legacy aliases
- stale helper code that is no longer part of mounted runtime
