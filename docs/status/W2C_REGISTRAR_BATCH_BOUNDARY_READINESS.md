# Wave 2C Registrar Batch Boundary Readiness

Date: 2026-03-08
Mode: post-correction readiness review
Decision: `READY_FOR_BOUNDARY_MIGRATION`

## What Is Now True

- active-entry contract for batch duplicate gate is clarified
- specialist-level claim model for this family is clarified
- mounted runtime now reuses compatible active rows in:
  - `waiting`
  - `called`
  - `in_service`
  - `diagnostics`
- ambiguity now returns explicit `409`

## Why The Family Is Ready Now

### 1. The main behavior drift is corrected

The mounted batch path no longer creates a second `waiting` row when the
patient already has a compatible active specialist-day claim.

### 2. Numbering and fairness were preserved

This correction did not change:

- legacy numbering algorithm
- `queue_time` handling
- fairness ordering

### 3. The family remains narrowly scoped

Still out of scope:

- QR allocator families
- `OnlineDay`
- force-majeure
- broader registrar wizard orchestration

That means boundary migration can stay narrow and behavior-preserving.

## Remaining Deferred Concerns

These are not blockers for the next narrow step:

- mounted runtime owner is still router-level
- cleaner service seam is not yet runtime owner

Those concerns are exactly what the next boundary-migration slice should reduce.

## Verdict

Registrar batch-only family is now ready for a narrow caller-path migration
through `QueueDomainService.allocate_ticket()`.
