# Wave 2C Wizard Seam Verification

Date: 2026-03-08
Mode: readiness recheck, docs-only
Status: `verified`

## Runtime Files Reviewed

- `backend/app/api/v1/endpoints/registrar_wizard.py`
- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- `backend/app/services/morning_assignment.py`
- `backend/app/services/queue_service.py`

## What Is Now Isolated

Mounted `/registrar/cart` no longer owns the same-day queue-assignment loop
inline.

Current outer call chain:

1. `/registrar/cart`
2. `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`
3. `MorningAssignmentService._assign_queues_for_visit(...)`

This means billing/cart orchestration no longer calls `MorningAssignmentService`
directly from inline endpoint code.

## What Remains Shared

The actual queue-row creation decision still lives inside:

- `MorningAssignmentService._assign_single_queue(...)`

That method still owns:

- queue claim resolution
- duplicate/reuse gate
- queue payload shaping
- direct `queue_service.create_queue_entry(...)` call

## Verification Result

The wizard-family now has a real wizard-specific outer seam.

That seam is sufficient for:

- localizing wizard-family queue-assignment orchestration
- isolating the mounted endpoint from inline allocator calls

It is not yet sufficient for:

- swapping the create branch directly to `QueueDomainService.allocate_ticket()`
  without touching shared `MorningAssignmentService`

## Seam Verdict

Allocator surface is isolated enough at the outer seam level, but not yet at
the exact create-branch replacement point.
