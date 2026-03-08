# Wave 2C Registrar Batch Runtime Conflicts

Date: 2026-03-08
Mode: analysis-first, docs-only

## Purpose

This document compares the clarified registrar batch-only contract with current
runtime behavior.

## Conflict 1 — `diagnostics` mismatch

### Target contract

`diagnostics` is active and must block a new allocation in the same
patient/specialist/day claim.

### Current runtime

Mounted duplicate reuse checks only:

- `waiting`
- `called`

Characterization already proved that an existing `diagnostics` row does **not**
block creation of a new `waiting` row.

### Severity

High.

### Why it matters

This is the main behavior drift between batch-only runtime and the clarified
domain contract.

## Conflict 2 — broader active-entry mismatch

### Target contract

Active statuses for batch duplicate gate should be:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

### Current runtime

Code excludes:

- `in_service`
- `diagnostics`

from the duplicate gate.

### Severity

Medium.

### Note

Only `diagnostics` is characterization-proven today, but the code path clearly
shows the same mismatch for `in_service`.

## Conflict 3 — router-level runtime owner mismatch

### Target contract

Batch-only behavior should eventually live behind a service boundary before
allocator boundary migration.

### Current runtime

Mounted endpoint still owns:

- patient/service validation
- specialist normalization
- grouping
- duplicate pre-check
- daily queue creation
- response shaping

An aligned service seam exists in `QueueBatchService`, but it is not runtime
truth yet.

### Severity

Medium.

## Previously Suspected Conflict — same-specialist grouping

### Earlier ambiguity

Characterization originally flagged that runtime groups by `specialist_id`
rather than by `queue_tag`.

### Clarified target contract

Registrar batch-only claim is now defined as specialist-level.

### Result

This is **not** a remaining runtime conflict for this subfamily.

It remains a global queue-architecture distinction, but not a local mismatch
after contract clarification.

## Other Observed Notes

### Source passthrough

Current runtime preserves request `source` on new rows and keeps the original
source on reused rows.

This matches the current batch-only intent and is not a contract conflict.

### Numbering and fairness

Current runtime still allocates through legacy SSOT `queue_service` and keeps:

- monotonic numbering
- one shared `current_time` for newly created rows in a batch
- existing `queue_time` on reused rows

Those semantics are not the blocker here.

## Result

Boundary migration is still blocked, but now for a narrower reason:

- first correct the batch-only active-entry gate
- then move the corrected caller behind the service/boundary seam
