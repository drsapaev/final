# Wave 2C Next Execution Unit After Wizard Recheck

Date: 2026-03-09
Status: `one more narrow wizard extraction/decomposition`

## Selected Next Step

B) one more narrow wizard extraction/decomposition

## Recommended Scope

Extract the wizard-local create-branch handoff from
`MorningAssignmentService._assign_single_queue(...)` into a wizard-local seam,
so that a later wizard-family boundary migration can replace only that final
handoff with `QueueDomainService.allocate_ticket(...)`.

## Why This Is The Next Step

- the outer seam already exists
- contracts are already correct
- billing coupling is no longer the primary blocker
- the last significant blocker is the hidden create-branch handoff

## Why Migration Was Not Chosen Yet

The exact replacement point is still inside shared morning-assignment logic.

Migrating now would touch broader shared behavior than this family should own.
