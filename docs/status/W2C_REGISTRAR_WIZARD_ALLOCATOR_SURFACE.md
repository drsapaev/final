# Wave 2C Registrar Wizard Allocator Surface

Date: 2026-03-08
Mode: readiness recheck, docs-only

## Current Production-Relevant Allocator Surface

Mounted wizard-family queue creation does not call `QueueDomainService`
directly.

Current call chain:

1. `backend/app/api/v1/endpoints/registrar_wizard.py`
   `POST /registrar/cart`
2. `MorningAssignmentService._assign_queues_for_visit(...)`
3. `MorningAssignmentService._assign_single_queue(...)`
4. `queue_service.create_queue_entry(..., auto_number=True, commit=False)`

## Shared Surface Warning

`MorningAssignmentService` is not wizard-only.

It is also used by:

- the morning assignment job
- `morning_assignment_api_service.py`
- duplicate / unmounted registrar wizard service code

That means replacing the direct allocator call inside
`MorningAssignmentService._assign_single_queue(...)` would affect more than the
mounted wizard family.

## Boundary Replacement Feasibility

Technically, the create branch could be switched to:

- `QueueDomainService.allocate_ticket(allocation_mode=\"create_entry\", ...)`

without changing numbering semantics, because the boundary still delegates to
the same legacy allocator.

## Why This Is Not Yet A Clean Wizard-Only Migration

Because the allocator call lives inside a shared service seam, not inside a
wizard-only caller seam.

So a direct replacement would be:

- behavior-preserving
- but not family-local

## Surface Verdict

Allocator surface is narrow enough to map clearly, but not isolated enough for
a clean wizard-only migration slice.

## Recommended Direction

Before wizard-family boundary migration, extract or isolate the wizard-specific
allocator handoff from the shared `MorningAssignmentService` surface.
