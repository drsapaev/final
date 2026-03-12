# Wave 2C Next Execution Unit After OnlineDay Review

Date: 2026-03-09
Mode: analysis-first, docs-only

## Decision

`B) isolate OnlineDay as separate legacy island`

## Why this is the best next step

- The review found a small but still mounted legacy runtime surface.
- The family is no longer needed for the main allocator-boundary track.
- The right next move is to freeze its ownership and explicitly keep it out of
  SSOT allocator migration work.

## Why the other options were not chosen

### `A) narrow OnlineDay characterization/fix slice`

Not chosen because the core question is no longer “what does it do?” but
“should it stay in the main queue track?”. This review answers that already.

### `C) dead-code cleanup preparation`

Not chosen because the family still has mounted write/read/admin paths.

### `D) human review needed`

Not chosen because the current evidence is sufficient to make a track-ownership
decision without touching runtime behavior.

## Practical implication

After this review, OnlineDay should be treated as:

- legacy compatibility ownership
- separate from `QueueDomainService.allocate_ticket()` migration work
- eligible for later legacy isolation / retirement planning

It should not block further main queue-track decisions.
