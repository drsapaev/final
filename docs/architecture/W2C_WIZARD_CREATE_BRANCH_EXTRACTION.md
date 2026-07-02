# Wave 2C Wizard Create Branch Extraction

Date: 2026-05-06
Mode: runtime replacement for stale PR #88

## Current-Main Contract

The mounted wizard queue path keeps shared queue-claim resolution in `MorningAssignmentService`, but makes the create-entry branch explicit for `RegistrarWizardQueueAssignmentService`.

Flow:

1. `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)` filters same-day confirmed visits.
2. It asks `MorningAssignmentService._get_visit_queue_tags(...)` for queue buckets.
3. It calls `MorningAssignmentService.prepare_wizard_queue_assignment(...)` for each bucket.
4. Existing active entries return an immediate reuse payload.
5. New entries return `MorningAssignmentCreateBranchHandoff`.
6. The wizard service materializes that handoff through `queue_service.create_queue_entry(...)`.

## Preserved Behavior

- Duplicate/reuse lookup remains in the shared morning-assignment claim logic.
- Number allocation still comes from `queue_service.create_queue_entry(...)`.
- `queue_time`, `services`, `service_codes`, `source`, and `commit=False` are preserved in the handoff kwargs.
- Future-day and non-confirmed visits are still skipped by the wizard service.

## Compatibility Note

This replacement does not carry the old stacked parent context. It only preserves the create-branch seam that is compatible with current `main`.
