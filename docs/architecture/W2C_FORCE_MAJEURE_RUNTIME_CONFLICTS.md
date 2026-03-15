# Wave 2C Force Majeure Runtime Conflicts

Date: 2026-03-09
Mode: contract-review

## What Already Matches The Target Contract

- transfer creates a new tomorrow row instead of mutating the old row in place
- old row is cancelled after transfer
- target row gets a new queue-local number
- target row gets a new transfer-time `queue_time`
- target row uses `source="force_majeure_transfer"`
- target row preserves `visit_id`
- priority override is explicit through `priority=2`

These all fit the intended exceptional-domain contract.

## Conflicts

### 1. Duplicate gate is missing on the target queue/day

- Current runtime: if the patient already has an active tomorrow row, transfer
  still creates another active row
- Target contract: this should not happen silently
- Classification: bug/drift

### 2. Numbering helper ignores cancelled rows

- Current runtime: `_get_next_queue_number()` filters `status != "cancelled"`
- Target contract: historical numbers in the target queue/day should remain
  monotonic and not be reused
- Classification: bug/drift

### 3. Pending-entry documentation overstates eligibility

- Current runtime selector uses only `waiting` and `called`
- Some service comments/docstrings mention broader statuses such as
  `in_service` and `diagnostics`
- Target contract: eligibility must be explicit; current code and docs disagree
- Classification: unresolved documentation/business decision, but not a reason
  to migrate

## Not Treated As Conflicts

These are intentional overrides, not bugs:

- new target `queue_time`
- priority boost
- distinct transfer source
- preserving visit linkage onto the new row

## Severity Summary

- High: missing target duplicate gate
- High: numbering monotonicity risk via cancelled-row exclusion
- Medium: eligibility/docs mismatch
