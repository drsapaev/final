# Wave 2C Registrar Wizard Decision Matrix

Date: 2026-03-08
Mode: contract review, docs-only

| Topic | Current runtime model | Target model | Severity | Action before migration |
|---|---|---|---|---|
| Claim ownership | queue-tag-driven resolved queue claim | queue-tag-driven resolved queue claim | low | no correction needed |
| Same specialist + different `queue_tag` | multiple active rows allowed | multiple active rows allowed | low | no correction needed |
| Duplicate gate | queue-local reuse without canonical active-status gate | queue-local reuse with canonical active-status gate | high | behavior correction required |
| Numbering | queue-local through legacy allocator | queue-local through compatibility boundary later | medium | keep for now |
| Fairness / `queue_time` | fresh time for new rows, preserved time for reused rows | same | low | no correction needed |
| Billing coupling | cart/invoice/queue assignment mixed in one mounted flow | still mixed today; extraction deferred | high | do not migrate boundary yet |

## Current Runtime Model

- queue-tag-driven claim
- queue-local reuse
- mixed billing + queue orchestration

## Target Model

- queue-tag-driven claim remains
- duplicate gate must use canonical active-entry semantics
- migration only after behavior correction

## Verdict

Behavior correction is required before any boundary migration.

What is rejected:

- forcing wizard-family into specialist-level claim ownership

What is accepted:

- intentional divergence from batch-family
- queue-tag-level claim ownership for wizard-family
