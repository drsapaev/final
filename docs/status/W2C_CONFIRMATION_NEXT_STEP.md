# Wave 2C Confirmation Next Step

Date: 2026-03-07
Mode: characterization-first
Recommended unit: `human review needed`

## Why

The current confirmation family is now characterized, but the next safe step is
not code migration yet.

The blocking question is domain-level:

- should confirmation preserve the current behavior of creating a new
  `source="confirmation"` active row even when the patient already has an active
  queue row in that same queue?

Without that answer, a boundary migration could either:

- silently preserve a behavior the team considers a bug
- or silently "fix" a behavior that current operator workflows depend on

## Recommended Human Review Questions

1. Is the current duplicate-preserving confirmation behavior accepted or should
   it become an explicit conflict?
2. Should registrar confirmation stay on its own bridge or be aligned with the
   public token-confirmation service before migration?
3. Should the confirmation migration target only `create_queue_entry` delegation
   or also own the pre-allocation step?

## Deferred Until After Review

- confirmation boundary migration slice
- broader registrar confirmation refactor
- any attempt to add new duplicate-policy enforcement inside confirmation flow
