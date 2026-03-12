# Wave 2C Next Execution Unit After OnlineDay Isolation

Date: 2026-03-09
Mode: analysis-first, docs-only

## Decision

`A) force_majeure isolation/follow-up`

## Why this is the best next step

- OnlineDay is now explicitly outside the main queue track.
- The main SSOT allocator track is effectively complete.
- `force_majeure` is the other remaining non-main-track queue domain that still
  needs explicit isolation / follow-up ownership treatment.

## Why the other options were not chosen

### `B) cleanup prep for dead/duplicate queue code`

Valuable, but lower priority than isolating the remaining exceptional-domain
flow first.

### `C) overall Wave 2C closure review`

Premature while `force_majeure` still has not gone through an explicit
post-classification isolation/follow-up pass.

### `D) human review needed`

Not needed; current evidence is sufficient to choose the next unit.
