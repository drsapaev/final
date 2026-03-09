# Wave 2C Wizard Create-Branch Extraction Plan

Date: 2026-03-09
Mode: behaviour-preserving extraction

## Current Handoff

Mounted `/registrar/cart` already delegates same-day queue assignment to
`RegistrarWizardQueueAssignmentService`, but the exact create-entry handoff is
still hidden inside `MorningAssignmentService._assign_single_queue(...)`.

That shared method currently:

- resolves wizard queue-tag claim and duplicate/reuse semantics
- builds create-entry kwargs for the legacy allocator
- calls `queue_service.create_queue_entry(...)` inline

## Extraction Target

Extract only the wizard-local create branch so that:

- `MorningAssignmentService` still owns shared queue-tag claim resolution
- `MorningAssignmentService` still owns shared duplicate/reuse logic
- wizard-family gets an explicit create-branch handoff object
- mounted wizard seam can materialize the create branch without touching
  billing/invoice orchestration

## What Remains Shared

- `MorningAssignmentService._get_visit_queue_tags(...)`
- `MorningAssignmentService._resolve_existing_queue_claim_or_raise(...)`
- daily queue resolution / creation
- legacy allocator implementation and numbering behavior

## What Becomes Wizard-Local

- explicit create-branch handoff from shared morning-assignment logic
- wizard-local materialization of that handoff inside
  `RegistrarWizardQueueAssignmentService`

## Why This Is Safe

- no numbering algorithm changes
- no queue_time or fairness changes
- no duplicate-policy redesign
- no billing or invoice refactor
- future-day behavior stays untouched
