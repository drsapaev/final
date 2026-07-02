# Wave 2C Registrar Wizard Runtime Conflicts

Date: 2026-03-08
Mode: contract review, docs-only

## Where Runtime Already Matches The Target Contract

### Queue-tag fan-out

Runtime already expands one visit into multiple queue claims by unique
`queue_tag`.

Assessment:

- matches target contract
- intentional domain difference from batch-family

### Multiple rows across different queue claims

Runtime allows more than one row when the visit resolves to different queue
claims.

Assessment:

- matches target contract
- not a bug

### Fresh `queue_time` for new queue claims

New wizard-created rows receive fresh `queue_time` and keep fairness local to the
new queue claim.

Assessment:

- matches target contract

### Future-day deferral

Future-day cart flow does not allocate a row immediately.

Assessment:

- compatible with the target contract

## Where Runtime Conflicts With The Target Contract

### Duplicate gate ignores canonical active-status contract

Current runtime reuse checks the first matching row in the resolved queue for the
patient without an explicit canonical active-status filter.

Conflict type:

- behavior conflict

Why it matters:

- terminal or otherwise non-canonical rows can influence reuse semantics
- this does not match the target active-entry contract

### Reuse ownership semantics are only implicit

When runtime reuses an existing row, it keeps existing row metadata as-is.
Current evidence confirms preservation behavior, but the design documents do not
define a stronger relinking rule.

Conflict type:

- partial contract gap, not a proven bug

Why it matters:

- reuse is allowed, but ownership semantics should stay explicit before
  migration

### Billing coupling remains in the mounted runtime owner

The same mounted `/registrar/cart` request still owns:

- visit creation
- invoice creation
- invoice-visit linking
- same-day queue assignment

Conflict type:

- structural migration blocker

Why it matters:

- even if duplicate semantics are corrected, boundary migration is still not a
  safe next step until this coupling is addressed or deliberately accepted

## Batch-Family Divergence

Wizard-family divergence from batch-family is:

- intentional
- not itself a bug

The conflict was not “wizard should become specialist-level.”
The real conflict is:

- wizard runtime has queue-tag-driven claims, but its duplicate gate is still
  looser than the canonical active-entry contract

## Conflict Verdict

Behavior correction is required before any wizard-family boundary migration.

The needed correction is narrow:

- keep queue-tag-level claim ownership
- tighten reuse to canonical active-row semantics inside the resolved queue claim

The broader billing-coupled migration problem remains a later concern.
