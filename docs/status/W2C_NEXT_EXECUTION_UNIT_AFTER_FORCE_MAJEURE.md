# Wave 2C Next Execution Unit After Force Majeure

Date: 2026-03-09
Mode: post-characterization
Status: `contract clarification pass`

## Decision

The next execution unit should be:

- `contract clarification pass`

## Why

- force-majeure is an exceptional transfer domain, not a normal allocator caller
- current runtime intentionally overrides fairness, queue time, source, and
  duplicate behavior
- a migration or seam extraction before clarifying those override rules would be
  risky

## Not Chosen

- `narrow force_majeure behavior-correction slice`
  - no safe correction target is clear before clarifying override intent
- `narrow seam extraction`
  - current seams are not the main blocker; policy ownership is
- `defer force_majeure and move to OnlineDay legacy review`
  - possible later, but force-majeure still has a clearer immediate next step
