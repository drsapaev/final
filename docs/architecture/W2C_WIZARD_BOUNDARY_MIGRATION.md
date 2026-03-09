# Wave 2C Wizard Boundary Migration

Date: 2026-03-09
Mode: behaviour-preserving migration

## Old Path

Mounted wizard-family same-day create branch used:

1. `/registrar/cart`
2. `RegistrarWizardQueueAssignmentService`
3. `MorningAssignmentService.prepare_wizard_queue_assignment(...)`
4. `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`
5. direct `queue_service.create_queue_entry(...)`

## New Path

Mounted wizard-family same-day create branch now uses:

1. `/registrar/cart`
2. `RegistrarWizardQueueAssignmentService`
3. `MorningAssignmentService.prepare_wizard_queue_assignment(...)`
4. `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`
5. `QueueDomainService.allocate_ticket(allocation_mode="create_entry", **kwargs)`
6. legacy `queue_service.create_queue_entry(...)` internally

## Why Behavior Is Preserved

- wizard-family still resolves queue claims by `queue_tag`
- same `queue_tag` reuse still happens before allocation
- different `queue_tag` rows still fan out separately
- the same create-entry kwargs are forwarded
- numbering still runs inside the same legacy allocator
- `queue_time` still comes from the same handoff builder
- observed billing/invoice behavior is untouched

## What Remains Outside Boundary

- broader registrar wizard/cart orchestration
- billing and invoice ownership
- future-day no-allocation logic
- batch-family flow
- confirmation-family flow
- `qr_queue.py` direct SQL family
- `OnlineDay` legacy family
- force-majeure family

## Architectural Result

Wizard-family is now aligned with the Wave 2C compatibility boundary for its
mounted same-day queue-allocation create branch.
