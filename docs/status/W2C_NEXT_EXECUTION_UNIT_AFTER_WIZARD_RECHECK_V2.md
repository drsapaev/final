# Wave 2C Next Execution Unit After Wizard Recheck V2

Date: 2026-05-06
Mode: docs-only replacement for stale PR #89

## Decision

Recommended next execution unit: `wizard boundary migration`.

## Why This Step

The mounted wizard-family now satisfies the prerequisites that blocked earlier passes:

- queue-tag claim model is explicit
- duplicate/reuse gate stays in shared claim resolution
- outer wizard seam exists
- create-branch handoff exists after #267
- `QueueDomainService.allocate_ticket(allocation_mode="create_entry")` exists and delegates to the same legacy allocator

The next narrow architectural step is therefore to replace the wizard-local create-branch materialization call with `QueueDomainService.allocate_ticket(...)` without changing billing orchestration or broader registrar behavior.

## Not Chosen

- `one more narrow wizard fix`: not chosen because no blocking narrow fix remains after #267.
- `defer wizard family and move to another allocator family`: not chosen because wizard-family is now better isolated than the remaining high-risk allocator families.
