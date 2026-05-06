# Wave 2C Registrar Wizard Numbering Check

Date: 2026-03-08
Mode: readiness recheck, docs-only
Status: `unchanged legacy numbering`

## Runtime Owners Reviewed

- `backend/app/api/v1/endpoints/registrar_wizard.py`
- `backend/app/services/morning_assignment.py`
- `backend/app/services/queue_service.py`

## Current Numbering Path

Mounted `/registrar/cart` does not calculate ticket numbers itself.

Runtime path:

1. `/registrar/cart` creates visits and invoice records
2. same-day confirmed visits call
   `MorningAssignmentService._assign_queues_for_visit(...)`
3. `_assign_single_queue(...)` either reuses an existing row or calls
   `queue_service.create_queue_entry(..., auto_number=True, commit=False)`
4. `queue_service.create_queue_entry(...)` delegates numbering to
   `get_next_queue_number(...)`

## Numbering Semantics Check

Confirmed:

- numbering remains in the legacy allocator
- wizard-family does not add a second numbering branch
- reuse path does not issue a new number
- create path still uses `auto_number=True`
- `queue_time` for new rows is still set in `MorningAssignmentService`
- `queue_time` for reused rows is preserved

## Billing Independence

Billing and invoice creation happen in the mounted `/registrar/cart` owner
before queue assignment, but the number itself is not derived from billing data.

Wizard-family queue allocation uses:

- queue claim resolution
- patient / visit context
- queue allocator service

It does not use:

- invoice total
- payment status
- billing calculations as numbering input

## Determinism Verdict

Wizard-family numbering is safe for migration only in the narrow sense that it
is unchanged and still delegated to the same legacy allocator path.

This document does not claim the legacy allocator is globally race-safe.

## Readiness Implication

Numbering semantics are not the main blocker for boundary migration.

The blockers are:

- shared allocator surface ownership
- mounted cart orchestration coupling
