# Wave 2C Wizard Allocator Surface

Date: 2026-05-06
Mode: replacement status

## Shared Surface

- `MorningAssignmentService._get_visit_queue_tags(...)`
- `MorningAssignmentService.prepare_wizard_queue_assignment(...)`
- `MorningAssignmentService._resolve_existing_queue_claim_or_raise(...)`

These keep queue-tag selection, active-entry reuse, and ambiguity handling in one place.

## Wizard-Local Surface

- `RegistrarWizardQueueAssignmentService._assign_same_day_queues_for_visit(...)`
- `RegistrarWizardQueueAssignmentService._materialize_prepared_assignment(...)`
- `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`

These make create-entry materialization explicit without duplicating claim resolution.

## Legacy Allocator

`queue_service.create_queue_entry(...)` remains the numbering allocator. This PR does not replace numbering policy or queue fairness behavior.
