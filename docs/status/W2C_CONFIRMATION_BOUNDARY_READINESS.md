# Wave 2C Confirmation Boundary Readiness

Date: 2026-05-05
Mode: post-correction and post-boundary-migration
Decision: `CONSUMED_BY_BOUNDARY_MIGRATION`

## Why The Status Changed

Earlier confirmation readiness was blocked by duplicate-creating behavior and
split public/registrar semantics. The replacement chain resolved that in two
steps:

1. #262 preserved the corrected active-entry reuse and explicit ambiguity
   conflict behavior on current `main`.
2. This boundary migration slice routes new confirmation queue-row creation
   through the queue compatibility boundary.

## Current Confirmation Properties

- clear existing active row is reused
- no new ticket is allocated in the reuse case
- ambiguous ownership returns explicit conflict
- public confirmation and mounted registrar confirmation share the same service
  assignment path
- when a new row is needed, creation goes through `QueueContextFacade` and
  `QueueDomainService.allocate_ticket()`

## What Still Remains Legacy

- standalone number lookup remains legacy
- allocator internals still delegate to the legacy queue service
- broader registrar wizard/batch allocation families remain deferred
- `qr_queue`, `force_majeure`, and `OnlineDay` allocator families remain out of
  scope

## Current Verdict

The mounted confirmation family no longer blocks the queue boundary track. The
next useful allocator step should be characterization-first for the next risky
family, not more confirmation plumbing.

## Later Progress

This readiness result has now been consumed by the boundary migration slice.
See:

- `docs/architecture/W2C_CONFIRMATION_BOUNDARY_MIGRATION.md`
- `docs/status/W2C_CONFIRMATION_BOUNDARY_MIGRATION_STATUS.md`
