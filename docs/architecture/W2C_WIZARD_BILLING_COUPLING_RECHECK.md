# Wave 2C Wizard Billing Coupling Recheck

Date: 2026-03-09
Mode: readiness review, docs-only

## Question

After the outer seam extraction, is billing/cart coupling still the main
blocker for wizard-family boundary migration?

## Current Mounted Shape

`/registrar/cart` still owns:

- visit creation
- invoice creation
- invoice-visit linking
- billing total calculation
- final response shaping

But it no longer owns the queue-assignment loop inline.

## Coupling Severity

Verdict: `MEDIUM`

## Why Not HIGH

- queue assignment now has a dedicated wizard-local outer seam
- allocator orchestration is no longer hidden directly inside the endpoint body
- migration analysis can focus on the seam instead of the whole cart method

## Why Not LOW

- queue assignment still runs inside the same request/session lifecycle
- invoice and queue outcomes are still committed together
- the mounted response still combines billing/visit/queue data

## Recheck Conclusion

Billing coupling still exists, but it is no longer the sharpest blocker.

The sharper blocker is the remaining hidden create-branch handoff inside shared
`MorningAssignmentService`.
