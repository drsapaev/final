# Wave 2C Registrar Batch Create-Action Decision

## Verdict

`BROKEN_RUNTIME_FIX_FIRST`

## Why

This pass established that the mounted create-action branch is:

- live;
- production-relevant;
- outside the boundary architecture;
- currently broken before allocator behavior executes.

Because the branch fails at runtime on import, it is **not** yet:

- a migration candidate;
- a behavior-correction candidate at allocator-policy level;
- or dead code safe to delete without a narrower fix/deprecation decision.

## What Must Happen Before Any Migration Decision

One narrow step is still required first:

- fix or explicitly retire the mounted create-action branch so that its runtime ownership becomes clear.

Only after that can the track decide between:

- boundary migration;
- cleanup/deprecation;
- or removal from registrar allocator scope.
