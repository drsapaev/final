# Wave 2C Wizard Allocator Surface

Date: 2026-03-09
Mode: post-extraction surface map

## Old Surface

Mounted `/registrar/cart` delegated same-day queue assignment to
`RegistrarWizardQueueAssignmentService`, but the exact create-entry handoff was
still hidden inside `MorningAssignmentService._assign_single_queue(...)`.

That meant the true wizard migration point was still buried in shared
morning-assignment logic.

## Current Surface

The mounted wizard-family allocator surface is now split into:

### Wizard-Local Outer Seam

- `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`
- `RegistrarWizardQueueAssignmentService._assign_same_day_queues_for_visit(...)`
- `RegistrarWizardQueueAssignmentService._materialize_prepared_assignment(...)`
- `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`

### Shared Resolution Surface

- `MorningAssignmentService._get_visit_queue_tags(...)`
- `MorningAssignmentService.prepare_wizard_queue_assignment(...)`
- `MorningAssignmentService._resolve_existing_queue_claim_or_raise(...)`
- `MorningAssignmentService._build_create_branch_handoff(...)`

### Legacy Allocator Surface

- `queue_service.create_queue_entry(...)`

## What This Means

The mounted wizard-family no longer depends on a hidden inline create branch.

The remaining shared dependency is now explicit and narrow:

- shared morning-assignment code still assembles create-entry kwargs
- wizard-local code now owns the caller handoff that materializes the create
  branch

## Migration Implication

The future boundary migration can now target one explicit wizard-local call
site instead of rewriting broader `/registrar/cart` or billing orchestration.

That still requires a readiness recheck before swapping the handoff to
`QueueDomainService.allocate_ticket(...)`.
