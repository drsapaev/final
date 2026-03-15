# Wave 2C Next Execution Unit After Wizard Create-Branch Extraction

Date: 2026-03-09

## Decision

Recommended next execution unit: `wizard boundary-readiness recheck`

## Why This Step

The previous blocker was the hidden create-branch handoff inside shared
`MorningAssignmentService`.

That blocker is now removed:

- wizard-family has an explicit outer seam
- wizard-family now has an explicit create-branch handoff seam
- behavior-preserving tests remain green

The next responsible step is not immediate migration, but a narrow readiness
recheck to verify:

- the extracted seam is isolated enough
- billing coupling is no longer the primary blocker
- `QueueDomainService.allocate_ticket(...)` can replace the wizard-local
  create branch without altering numbering or fairness semantics

## Not Chosen

- `wizard boundary migration`
  Not chosen because this slice was extraction-only and readiness still needs
  an explicit recheck.

- `further wizard decomposition needed`
  Not chosen because the known create-branch blocker has already been isolated.

- `defer wizard and move to another allocator family`
  Not chosen because wizard-family is now close to a clean boundary decision.
