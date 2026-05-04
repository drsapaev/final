# Wave 2C Wizard Billing Coupling Recheck

Date: 2026-03-08
Mode: readiness recheck, docs-only

## Mounted Runtime Reviewed

- `POST /api/v1/registrar/cart`
- `RegistrarWizardQueueAssignmentService`

## Recheck Question

Did extraction materially reduce billing coupling for queue migration
readiness?

## Current State

The mounted endpoint still owns:

- visit creation
- invoice creation
- invoice-visit linking
- billing calculations
- final response assembly

But it no longer owns the queue-assignment loop inline.

Queue handoff now occurs through a wizard-specific service seam.

## Severity

Verdict: `MEDIUM`

## Why Not HIGH

- allocator handoff is no longer inline in the billing-heavy endpoint
- wizard-family queue assignment now has a dedicated outer seam
- queue-specific behavior can be reasoned about separately from the cart body

## Why Not LOW

- queue assignment still happens inside the same mounted request/session
- billing artifacts and queue artifacts are still committed together
- the endpoint still returns invoice, visit, and queue data together

## Coupling Implication

Billing coupling still exists, but it is no longer the main reason to defer all
queue-boundary work on wizard-family.

The sharper blocker is now the remaining shared create-branch logic inside
`MorningAssignmentService`.
