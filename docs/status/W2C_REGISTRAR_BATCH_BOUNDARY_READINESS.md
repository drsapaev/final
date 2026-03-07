# Wave 2C Registrar Batch Boundary Readiness

Date: 2026-03-07
Mode: characterization-first
Decision: `READY_AFTER_CONTRACT_CLARIFICATION`

## Why It Is Not Ready Yet

### 1. Active-entry contract conflict

Mounted runtime duplicate detection reuses only:

- `waiting`
- `called`

Characterization now shows:

- existing `diagnostics` row does not block new allocation

That conflicts with the canonical active-entry contract where `diagnostics` is
active.

### 2. Grouping contract is still ambiguous

Mounted runtime groups by resolved `specialist_id`, not by `queue_tag` or
canonical queue claim.

Characterization shows:

- two services for the same specialist but different `queue_tag` values still
  produce one queue row

That behavior may be correct, but it needs an explicit contract decision before
boundary migration freezes it.

### 3. Mounted runtime owner is still the router

The mounted API path still owns:

- patient/service validation
- specialist normalization
- duplicate pre-check
- daily queue creation
- response shaping

A cleaner `QueueBatchService` seam exists, but it is not runtime truth.

## What Is Favorable

- direct billing/payment side effects are not part of this subfamily
- visit linkage is not part of this subfamily
- row creation still goes through SSOT `queue_service.create_queue_entry(...)`
- repeated batch submission is stable for `waiting/called` duplicates

## What Contract Clarification Is Needed

1. Should batch-only duplicate reuse treat `diagnostics` and `in_service` as
   active blockers?
2. Is same-specialist grouping intended to collapse different `queue_tag`
   services into one row?
3. Should registrar batch endpoint continue accepting `source="morning_assignment"`
   as passthrough input?

## Verdict

`QueueDomainService.allocate_ticket()` should **not** be the next registrar
batch change yet.

The family is close enough for targeted follow-up work, but only after the
batch-specific contract is clarified.
