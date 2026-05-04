# Wave 2C Registrar Wizard Boundary Readiness V2

Date: 2026-03-08
Mode: readiness recheck, docs-only

## Inputs Reviewed

- `docs/architecture/W2C_REGISTRAR_WIZARD_CLAIM_CONTRACT.md`
- `docs/status/W2C_REGISTRAR_WIZARD_CLAIM_CONTRACT_CHECK.md`
- `docs/status/W2C_REGISTRAR_WIZARD_DUPLICATE_POLICY_CHECK.md`
- `docs/status/W2C_REGISTRAR_WIZARD_NUMBERING_CHECK.md`
- `docs/architecture/W2C_REGISTRAR_WIZARD_BILLING_COUPLING.md`
- `docs/status/W2C_REGISTRAR_WIZARD_ALLOCATOR_SURFACE.md`
- `docs/architecture/W2C_ALLOCATOR_COMPATIBILITY_LAYER.md`
- `docs/architecture/W2C_QUEUE_DOMAIN_SERVICE.md`

## Decision

Verdict: `REQUIRES_PARTIAL_DECOMPOSITION`

## Why Not READY_FOR_BOUNDARY_MIGRATION

Queue-domain blockers are reduced, but the mounted wizard family still does not
own an isolated allocator call site.

The production-relevant create branch lives inside shared
`MorningAssignmentService`, which is reused outside wizard-family.

## Why Not BLOCKED_BY_BILLING_COUPLING Alone

Billing coupling is real and high, but it is not the only blocker.

The deeper technical issue is that wizard-family does not yet have a clean,
family-local allocator seam for migration.

## What Is Already Ready

- queue-tag claim contract
- canonical active-status duplicate gate
- reuse-existing-entry behavior
- unchanged numbering semantics through the legacy allocator

## What Still Needs Work

- isolate wizard-family allocator handoff from shared `MorningAssignmentService`
- keep mounted `/registrar/cart` behavior intact while narrowing the queue
  integration seam

## Readiness Summary

Wizard-family is no longer blocked by claim ambiguity or duplicate drift.

Wizard-family is also not blocked by numbering drift.

It is blocked by the need for one more narrow decomposition step before a clean
boundary migration can happen without implicitly migrating other
`MorningAssignmentService` callers.
