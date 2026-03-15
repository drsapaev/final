# Wave 2C Wizard Boundary Feasibility

Date: 2026-03-09
Mode: readiness review, docs-only

## Question

Can mounted wizard-family now be switched to:

- `QueueDomainService.allocate_ticket()`

without changing:

- numbering behavior
- `queue_time`
- fairness ordering
- duplicate semantics
- source semantics
- future-day behavior

## Feasibility Assessment

Not in one clean step yet.

## Why

The outer seam is now explicit, but the exact wizard create-branch handoff is
still hidden inside shared `MorningAssignmentService._assign_single_queue(...)`.

That shared method currently bundles:

- queue claim resolution
- duplicate / reuse gate
- service-code payload preparation
- direct `queue_service.create_queue_entry(...)`

So replacing only the outer seam would still require touching shared internal
morning-assignment logic.

## What Is Already Feasible

The future migration entry point is now explicit:

- `RegistrarWizardQueueAssignmentService`

And the target boundary is signature-compatible:

- `QueueDomainService.allocate_ticket(allocation_mode="create_entry", **kwargs)`

## What Still Needs To Be Extracted

One more wizard-local narrow handoff is needed so that wizard-family can swap
only the final create-entry branch to `QueueDomainService.allocate_ticket(...)`
without altering shared morning-assignment behavior.

## Feasibility Verdict

Wizard boundary migration is feasible after one more narrow extraction.
