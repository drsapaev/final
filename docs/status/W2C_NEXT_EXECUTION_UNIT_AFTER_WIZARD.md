# Wave 2C Next Execution Unit After Wizard Readiness Recheck

Date: 2026-03-08
Status: `Wizard allocator extraction`

## Selected Next Step

C) Wizard allocator extraction

## Why This Is The Next Step

- wizard-family claim contract is validated
- duplicate policy is validated for the mounted same-day path
- numbering semantics are unchanged and already compatible with the legacy
  allocator
- the remaining blocker is the shared allocator surface inside
  `MorningAssignmentService`

## Why Wizard Boundary Migration Was Not Chosen

Direct migration now would touch a shared service seam used outside wizard
family.

That would no longer be a clean wizard-only migration slice.

## Why Wizard Cart/Billing Decoupling Was Not Chosen

Billing coupling is high, but the narrowest queue-architecture blocker is still
allocator surface ownership.

Allocator extraction is a smaller and more directly relevant step than broad
cart/billing decoupling.

## Why Moving To Another Family Was Not Chosen

Wizard-family is close to migration readiness.

One narrow decomposition pass should decide whether the boundary migration can
be done safely after that.
