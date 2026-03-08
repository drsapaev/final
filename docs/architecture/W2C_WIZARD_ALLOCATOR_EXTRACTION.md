# Wave 2C Wizard Allocator Extraction

Date: 2026-03-08
Mode: behavior-preserving decomposition

## Old Allocator Surface

Before this slice, the mounted `/registrar/cart` endpoint directly contained
the same-day queue-assignment loop.

That meant the production-relevant wizard-family allocator handoff lived
inline inside:

- visit creation
- invoice creation
- billing calculation
- final cart response assembly

## New Extracted Seam

The mounted queue-assignment handoff now lives in:

- `backend/app/services/registrar_wizard_queue_assignment_service.py`

Public seam:

- `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`

## New Call Chain

1. `backend/app/api/v1/endpoints/registrar_wizard.py`
2. `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`
3. `MorningAssignmentService._assign_queues_for_visit(...)`
4. `MorningAssignmentService._assign_single_queue(...)`
5. `queue_service.create_queue_entry(..., auto_number=True, commit=False)`

## Why Behavior Is Preserved

The new wizard seam is only an orchestration extraction.

It preserves:

- queue-tag-level claim ownership
- canonical active-status reuse gate
- same-queue-tag reuse
- different `queue_tag` fan-out
- `source="desk"` allocation semantics
- same-day-only queue assignment
- future-day no-immediate-allocation behavior
- legacy numbering and `queue_time` generation inside the existing allocator

## What Still Remains Coupled

The mounted `/registrar/cart` flow is still billing-heavy.

It still owns:

- visit creation
- invoice creation
- invoice-visit linking
- billing calculation

This slice narrows the queue entry point, but it does not redesign the cart
owner.

## Why This Makes Wizard-Family Closer To Boundary Migration

Before this slice, boundary migration would have required touching a shared
inline call site inside the mounted cart flow.

After this slice, wizard-family has a dedicated queue-assignment seam that can
be re-evaluated independently.

That is a cleaner starting point for the next readiness review.
