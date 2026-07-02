# Wave 2C Next Execution Unit After Batch Create-Action


Date: 2026-05-06
Current-main replacement for stale PR #92 after parent #91 was superseded by merged PR #270.
## Decision

`narrow fix for mounted batch create-action`

## Why

The mounted registrar batch create-action path is:

- live;
- production-relevant;
- outside the queue boundary architecture;
- broken before runtime allocation executes.

That makes a narrow runtime fix the only justified next step.

## Not Recommended Next

- `registrar track complete -> move to qr_queue family`
  not yet justified while one mounted registrar allocator branch is still broken
- `deprecate/cleanup dead path`
  not justified because the branch is mounted and reachable, not dead
- `human review needed`
  not required yet; the immediate gap is technical runtime correction, not contract ambiguity
