# Wave 2C Wizard Boundary Feasibility V2

Date: 2026-05-06
Mode: docs-only replacement for stale PR #89

## Question

Can the extracted wizard-local create-branch handoff now be replaced with `QueueDomainService.allocate_ticket(...)` without changing runtime semantics?

## Answer

Yes, as the next narrow runtime slice.

## Why

Current mounted wizard-family create path is:

1. build `MorningAssignmentCreateBranchHandoff`
2. materialize it through `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`
3. call `queue_service.create_queue_entry(self.db, **handoff.create_entry_kwargs)`

Current queue-domain boundary implementation is:

- `QueueDomainService.allocate_ticket(allocation_mode="create_entry", **kwargs)`
- delegates to the same legacy `queue_service.create_queue_entry(...)`

## Semantics Check

- Numbering behavior: safe to preserve because the same `create_queue_entry(..., auto_number=True)` call remains underneath the boundary.
- `queue_time` behavior: safe to preserve because `queue_time` is computed before the call and carried in the handoff kwargs.
- Fairness ordering: safe to preserve because no ordering logic needs to move for the boundary swap.
- Duplicate semantics: safe to preserve because duplicate/reuse logic runs before create-branch materialization.
- Source semantics: safe to preserve because `source` already travels in the handoff payload.
- Future-day behavior: safe to preserve because the wizard service still filters same-day confirmed visits.

## Required Runtime Proof For Next PR

The next runtime PR should prove that replacing `_allocate_create_branch_handoff(...)` with `QueueDomainService.allocate_ticket(...)` preserves the handoff kwargs and assigned payload.
