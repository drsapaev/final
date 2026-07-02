# Wave 2C Registrar Wizard Allocator Surface

Date: 2026-03-08
Mode: readiness recheck, docs-only

## Current Production-Relevant Allocator Surface

Mounted wizard-family queue creation still does not call `QueueDomainService`
directly, but it now owns a cleaner queue-assignment seam.

Current call chain:

1. `backend/app/api/v1/endpoints/registrar_wizard.py`
   `POST /registrar/cart`
2. `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`
3. `MorningAssignmentService._assign_queues_for_visit(...)`
4. `MorningAssignmentService._assign_single_queue(...)`
5. `queue_service.create_queue_entry(..., auto_number=True, commit=False)`

## Shared Surface Warning

`MorningAssignmentService` is still not wizard-only.

It is also used by:

- the morning assignment job
- `morning_assignment_api_service.py`
- duplicate / unmounted registrar wizard service code

That means replacing the allocator call inside
`MorningAssignmentService._assign_single_queue(...)` directly would still affect
more than the mounted wizard family.

However, the mounted wizard-family now reaches that shared logic through a
wizard-specific service seam rather than inline endpoint code.

## Boundary Replacement Feasibility

Technically, the create branch could be switched to:

- `QueueDomainService.allocate_ticket(allocation_mode=\"create_entry\", ...)`

without changing numbering semantics, because the boundary still delegates to
the same legacy allocator.

## What The Extraction Changed

The production-relevant wizard-family now has a local seam:

- `RegistrarWizardQueueAssignmentService`

That narrows the migration target substantially because the mounted endpoint no
longer owns the allocator handoff inline.

## Surface Verdict

Allocator surface is now clean enough for a follow-up readiness recheck.

The remaining question is no longer "where is the call site?" but "is the new
seam sufficient for direct boundary migration without dragging billing coupling
into scope?"

## Recommended Direction

Run a narrow wizard boundary-readiness recheck on the extracted seam before any
boundary migration.
