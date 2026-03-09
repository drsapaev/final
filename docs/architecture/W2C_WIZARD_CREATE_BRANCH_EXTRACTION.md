# Wave 2C Wizard Create-Branch Extraction

Date: 2026-03-09
Mode: behaviour-preserving extraction

## Old Hidden Handoff

Before this slice, mounted `/registrar/cart` already delegated same-day queue
assignment to `RegistrarWizardQueueAssignmentService`, but the create-entry
branch itself was still hidden inside
`MorningAssignmentService._assign_single_queue(...)`.

That meant wizard-family still depended on a shared morning-assignment method
for all of the following in one place:

- queue-tag claim resolution
- duplicate/reuse gate
- daily queue resolution
- create-entry kwargs assembly
- direct call to `queue_service.create_queue_entry(...)`

## New Explicit Wizard-Local Seam

This slice split the last two concerns apart:

- `MorningAssignmentService.prepare_wizard_queue_assignment(...)` now resolves
  the queue-tag claim and returns either:
  - an existing-assignment payload, or
  - `MorningAssignmentCreateBranchHandoff`
- `RegistrarWizardQueueAssignmentService` now materializes the create branch
  through its own explicit handoff path

The mounted wizard-family path now looks like this:

1. `/registrar/cart`
2. `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`
3. `MorningAssignmentService.prepare_wizard_queue_assignment(...)`
4. if existing row exists -> reuse payload returned immediately
5. if create branch is needed -> wizard-local handoff is materialized via
   `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`
6. allocator still delegates to legacy `queue_service.create_queue_entry(...)`

## What Stayed Shared

- queue-tag-level claim resolution
- canonical active-status duplicate gate
- daily queue resolution / creation
- legacy numbering implementation
- future-day no-immediate-allocation behavior

## What Became Explicitly Wizard-Local

- the create-branch handoff object
- the mounted wizard caller that materializes the handoff
- the exact future replacement point for
  `QueueDomainService.allocate_ticket(...)`

## Why Behavior Was Preserved

- the same legacy allocator is still used
- `auto_number=True` is preserved
- `commit=False` is preserved
- `queue_time` is still generated in the same shared logic
- queue-tag-level reuse rules are unchanged
- different `queue_tag` fan-out remains unchanged
- billing/invoice orchestration is untouched

## Remaining Shared Boundary

Wizard-family is closer to boundary migration, but this slice did not migrate
to `QueueDomainService.allocate_ticket(...)`.

The remaining question is no longer "where is the create call hidden?" but
"is the extracted seam now isolated enough for a direct boundary swap without
behavior drift?"
