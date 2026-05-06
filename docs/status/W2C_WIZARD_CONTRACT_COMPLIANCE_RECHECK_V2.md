# Wave 2C Wizard Contract Compliance Recheck V2

Date: 2026-05-06
Mode: docs-only replacement for stale PR #89

## Contract Surfaces

| Surface | Current owner | Status |
|---|---|---|
| Same-day confirmed visit filtering | `RegistrarWizardQueueAssignmentService` | ready |
| Queue-tag discovery | `MorningAssignmentService._get_visit_queue_tags(...)` | shared, explicit |
| Duplicate/reuse claim | `MorningAssignmentService.prepare_wizard_queue_assignment(...)` | shared, explicit |
| Create-entry handoff | `MorningAssignmentCreateBranchHandoff` | ready |
| Create-entry materialization | `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)` | next migration target |
| Domain allocation boundary | `QueueDomainService.allocate_ticket(...)` | available |

## Compliance Result

The wizard family is compliant enough for a narrow boundary migration. The next PR should only replace the materialization call site and should not change claim resolution or payload assembly.

## Required Proof

- Existing entry path still returns status `existing`.
- Create path still returns status `assigned` with the same `queue_tag`, `queue_id`, and `number` shape.
- `source`, `queue_time`, `services`, `service_codes`, `visit_id`, and `commit=False` are preserved.
- Non-confirmed and future-day visits remain skipped.
