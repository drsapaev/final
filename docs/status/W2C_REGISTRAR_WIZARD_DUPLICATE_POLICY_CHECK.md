# Wave 2C Registrar Wizard Duplicate Policy Check

Date: 2026-03-08
Mode: readiness recheck, docs-only
Status: `validated for mounted same-day wizard path`

## Contracts Under Review

- `docs/architecture/W2C_DUPLICATE_POLICY_CONTRACT.md`
- `docs/architecture/W2C_ACTIVE_ENTRY_CONTRACT.md`

## Runtime Evidence

The mounted wizard-family duplicate/reuse gate now uses canonical active
statuses inside `MorningAssignmentService`:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

Runtime owner:

- `backend/app/services/morning_assignment.py`

Evidence:

- `WIZARD_DUPLICATE_ACTIVE_STATUSES` defines the canonical active set
- `_resolve_existing_queue_claim_or_raise(...)` filters
  `OnlineQueueEntry.status.in_(WIZARD_DUPLICATE_ACTIVE_STATUSES)`
- `_assign_single_queue(...)` reuses the matching row when exactly one
  compatible active row exists
- ambiguity raises `MorningAssignmentClaimError`
- mounted `/registrar/cart` handles that ambiguity through safe no-allocation
  behavior rather than creating a duplicate row

## Compliance Result

For the mounted same-day wizard path:

- duplicate gate is queue-tag-level
- canonical active statuses are used
- same-claim reuse works
- ambiguous same-claim ownership does not allocate a new row

## Limits Of This Check

This validation is local to the production-relevant mounted wizard path.

It does not claim that:

- all registrar-related helpers use the same gate
- batch-family or QR-family semantics are unified
- the broader cart owner is already decomposed

## Verdict

Wizard-family duplicate policy is compliant enough for readiness review.

The remaining blocker is not duplicate semantics.
