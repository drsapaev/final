# Wave 2C Next Execution Unit After Wizard Recheck

Date: 2026-03-08
Status: `one more narrow wizard extraction/decomposition`

## Selected Next Step

B) one more narrow wizard extraction/decomposition

## Recommended Scope

Extract the wizard-local create-branch handoff from
`MorningAssignmentService._assign_single_queue(...)` so that wizard-family can
later swap only that handoff to `QueueDomainService.allocate_ticket(...)`
without changing:

- claim resolution
- duplicate/reuse behavior
- payload shaping
- numbering semantics

## Why This Is The Next Step

- the outer wizard seam already exists
- boundary migration is close, but not yet clean
- one more narrow extraction removes the last shared create-branch blocker

## Why Migration Was Not Chosen Yet

The exact boundary replacement point is still hidden inside shared
`MorningAssignmentService`.

Direct migration now would be broader than a true wizard-family-only slice.

## Why Deferral Was Not Chosen

The remaining blocker is narrow, local, and already well-characterized.
