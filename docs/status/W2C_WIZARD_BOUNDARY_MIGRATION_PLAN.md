# Wave 2C Wizard Boundary Migration Plan

Date: 2026-03-09
Mode: behaviour-preserving migration

## Files In Scope

- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- wizard-related tests
- wizard boundary migration docs

## Exact Migration Point

The exact migration point is:

- `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`

Old behavior:

- wizard-local seam called `queue_service.create_queue_entry(...)` directly

New target behavior:

- wizard-local seam calls `QueueDomainService.allocate_ticket(...)`

## Why This Is Safe

- duplicate/reuse logic already runs before this point
- the handoff payload already contains `queue_time`, `source`, and
  `auto_number=True`
- `QueueDomainService.allocate_ticket(allocation_mode="create_entry", **kwargs)`
  delegates to the same legacy allocator internally

## Why This Is Behaviour-Preserving

- numbering algorithm is unchanged
- `queue_time` semantics are unchanged
- fairness ordering is unchanged
- future-day behavior is unchanged
- billing/invoice orchestration remains outside the migration point

## Explicitly Out Of Scope

- broader wizard/cart refactor
- billing / invoice redesign
- batch-family migration
- confirmation-family changes
- `qr_queue.py` direct SQL allocators
- `OnlineDay` legacy paths
- force-majeure allocators
