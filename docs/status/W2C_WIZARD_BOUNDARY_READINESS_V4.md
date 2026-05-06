# Wave 2C Wizard Boundary Readiness V4

Date: 2026-05-06
Mode: docs-only replacement for stale PR #89

## Readiness Result

Wizard boundary migration is ready for one narrow runtime PR.

## Ready Because

- Current `main` has an explicit wizard service seam.
- Current `main` has `MorningAssignmentCreateBranchHandoff`.
- Current `main` has `QueueDomainService.allocate_ticket(allocation_mode="create_entry")`.
- The proposed boundary swap can preserve the same `create_entry_kwargs` and assigned queue payload.

## Not Ready For

- broad registrar cart rewrite
- billing/invoice orchestration changes
- frontend flow changes
- queue numbering policy redesign
- migration changes

## Merge Guidance

A future runtime PR should be marked risky until it proves parity between direct `queue_service.create_queue_entry(...)` materialization and `QueueDomainService.allocate_ticket(...)` materialization.
