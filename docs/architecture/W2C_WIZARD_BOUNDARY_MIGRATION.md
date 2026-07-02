# W2C Wizard Boundary Migration

Date: 2026-05-06
Replacement for stale PR #90 after parent #89 was superseded by PR #268.

## Scope

This slice migrates the mounted same-day registrar wizard create-branch materialization to the queue domain boundary.

In scope:

- `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`
- `QueueDomainService.allocate_ticket(allocation_mode="create_entry")`
- focused unit proof for the default queue-domain path

Out of scope:

- router-level shadow branch deletion
- allocator implementation rewrites
- RBAC, notification, realtime, or frontend behavior changes

## Contract

The wizard preparation layer still returns `MorningAssignmentCreateBranchHandoff` with `create_entry_kwargs`. The registrar wizard orchestration layer is responsible for materializing that handoff through the queue domain service.

The external user-visible queue-number payload is unchanged:

- `queue_tag`
- `queue_id`
- `number`
- `status: assigned`

## Compatibility

The legacy `create_entry_allocator` injection remains available for focused characterization tests. Production default behavior now constructs `QueueDomainService(session)` and calls `allocate_ticket(allocation_mode="create_entry", **handoff.create_entry_kwargs)`.
