# Wave 2C Confirmation Boundary Readiness

Date: 2026-03-07
Mode: post-correction review
Decision: `READY_FOR_BOUNDARY_MIGRATION`

## Why The Readiness Status Changed

Earlier characterization blocked boundary migration because:

1. confirmation could create a second active queue row in the same queue/day
2. duplicate-versus-reuse intent was still unclear
3. public and registrar confirmation paths did not share corrected semantics

This slice corrected the mounted confirmation behavior without changing the
legacy allocator algorithm.

## Current Confirmation Properties

- clear existing active row is reused
- no new ticket is allocated in reuse case
- ambiguous ownership returns explicit conflict
- no same-queue duplicate active row is created by mounted confirmation flows
- public and registrar confirmation now use the same corrected assignment logic

## What Still Remains Legacy

- ticket allocation still uses legacy queue-service calls when a new row is
  actually needed
- validation and persistence ordering are still legacy
- allocator race characteristics are unchanged by this slice

These remaining items do not block a later narrow boundary migration anymore.

## Current Verdict

`QueueDomainService.allocate_ticket()` can now be introduced as a later
compatibility boundary for the mounted confirmation family without preserving
the old duplicate-creating drift.

## Later Progress

This readiness result has now been consumed by the boundary migration slice.
See:

- `docs/architecture/W2C_CONFIRMATION_BOUNDARY_MIGRATION.md`
- `docs/status/W2C_CONFIRMATION_BOUNDARY_MIGRATION_STATUS.md`
