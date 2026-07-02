# Wave 2C Wizard Boundary Feasibility

Date: 2026-03-08
Mode: readiness recheck, docs-only

## Question

Can the extracted wizard seam be switched to:

- `QueueDomainService.allocate_ticket()`

without changing:

- numbering behavior
- `queue_time` behavior
- fairness ordering
- duplicate semantics
- source semantics
- future-day behavior

## Feasibility Assessment

Not directly yet.

## Why Not Directly

`RegistrarWizardQueueAssignmentService` is now the correct outer seam, but it
still delegates the full create/reuse branch into
`MorningAssignmentService._assign_queues_for_visit(...)`.

That shared method still bundles:

- claim resolution
- active-entry reuse
- payload preparation
- direct `queue_service.create_queue_entry(...)`

So replacing only the outer seam with `QueueDomainService.allocate_ticket()`
would be incomplete unless wizard-family also extracts the exact create-branch
handoff from `MorningAssignmentService`.

## What Is Already Feasible

The future migration point is now clear:

- wizard-specific outer seam in `RegistrarWizardQueueAssignmentService`

## What Still Needs Extraction

One more narrow wizard-local seam is needed around the create branch, so that
wizard-family can:

1. keep current claim/reuse behavior
2. preserve payload shaping
3. replace only the final create-entry call with
   `QueueDomainService.allocate_ticket(...)`

## Feasibility Verdict

Boundary migration is feasible after one more narrow extraction.

It is not yet a clean one-step migration from the current extracted seam.
