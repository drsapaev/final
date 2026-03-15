# Wave 2C Force Majeure Follow-Up Track

Date: 2026-03-09
Mode: analysis-first, docs-only

## Purpose

This document defines the future follow-up track for the force_majeure
exceptional-domain island.

It does not start correction or migration now.

## What should be corrected later

### 1. Target-queue duplicate gate

Current runtime can create a second active tomorrow-row for the same patient on
the target queue/day.

This is the clearest future correction candidate.

### 2. Numbering monotonicity handling

`_get_next_queue_number()` ignores cancelled rows when computing the next
number.

If the target contract keeps monotonic historical numbering, this needs a later
correction.

## What requires business / human decision

### Pending-entry eligibility

Documentation and comments imply a broader eligible set than the runtime
`waiting/called` selector.

This needs explicit business confirmation before behavior is changed.

### Priority policy

Current `TRANSFER_PRIORITY = 2` looks intentional, but its long-term operator
meaning should still be confirmed before any future redesign.

## Tests needed before behavior change

At minimum:

- characterization for transfer duplicate collision on target queue/day
- characterization for numbering monotonicity with cancelled-history rows
- characterization for pending-entry eligibility decisions
- regression coverage for refund/deposit side effects
- notification side-effect smoke coverage

## Follow-up track verdict

Force majeure follow-up should be a local exceptional-domain track, not a
continuation of the ordinary allocator-boundary rollout.
