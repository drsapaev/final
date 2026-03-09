# Wave 2C Wizard Boundary Feasibility V2

Date: 2026-03-09
Mode: readiness review, docs-only

## Question

Can the extracted wizard-local create-branch handoff now be replaced with:

- `QueueDomainService.allocate_ticket(...)`

without changing runtime semantics?

## Answer

Yes.

## Why

Current mounted wizard-family create path is:

1. build `MorningAssignmentCreateBranchHandoff`
2. materialize it through
   `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`
3. that method calls:
   `queue_service.create_queue_entry(self.db, **handoff.create_entry_kwargs)`

Current queue-domain boundary implementation is:

- `QueueDomainService.allocate_ticket(allocation_mode=\"create_entry\", **kwargs)`
- which delegates to the same legacy `queue_service.create_queue_entry(...)`

## Semantics Check

### numbering behavior

Safe to preserve.

The same `create_queue_entry(..., auto_number=True)` call remains underneath the
boundary.

### `queue_time` behavior

Safe to preserve.

`queue_time` is already computed before the call and passed via the handoff.

### fairness ordering

Safe to preserve.

No ordering logic changes are required for the boundary swap.

### duplicate semantics

Safe to preserve.

Duplicate/reuse logic already runs before the create-branch materialization
step.

### source semantics

Safe to preserve.

The same `source` value is already carried in the handoff payload.

### future-day behavior

Safe to preserve.

Future-day deferral happens before the same-day wizard seam is invoked.

### billing / invoice observed behavior

Safe to preserve at observable level.

Billing orchestration remains in the mounted request flow, but the create-branch
swap is now narrow enough that it does not require billing redesign.

## Feasibility Verdict

Boundary migration is technically feasible without additional decomposition.
