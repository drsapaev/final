# Wave 2C Next Execution Unit After Wizard Recheck V2

Date: 2026-03-09

## Decision

Recommended next execution unit: `wizard boundary migration`

## Why This Step

The mounted wizard-family now satisfies the prerequisites that blocked earlier
passes:

- claim model clarified
- duplicate/reuse gate corrected
- outer seam extracted
- create-branch handoff extracted
- boundary feasibility confirmed

The next narrow architectural step is therefore to replace the wizard-local
create-branch materialization call with:

- `QueueDomainService.allocate_ticket(...)`

without changing billing orchestration or broader registrar behavior.

## Not Chosen

- `one more narrow wizard fix`
  Not chosen because no blocking narrow fix remains after the latest recheck.

- `defer wizard family and move to another allocator family`
  Not chosen because wizard-family is now ready and better isolated than the
  remaining high-risk allocator families.
