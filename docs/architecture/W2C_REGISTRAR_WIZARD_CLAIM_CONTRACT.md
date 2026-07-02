# Wave 2C Registrar Wizard Claim Contract

Date: 2026-03-08
Mode: contract review, docs-only

## Target Model

Registrar wizard-family queue claim is:

- `patient_id + resolved_queue_claim + queue_day`

For this family, `resolved_queue_claim` is the queue selected by `queue_tag`
for the relevant day.

## Canonical Claim Identity

Canonical identity:

- `patient_id`

Canonical claim:

- resolved queue for the visit’s `queue_tag`

Canonical day:

- `DailyQueue.day`

## Same Specialist + Different Queue Tags

Behavior:

- multiple rows are allowed

Why:

- different `queue_tag` values represent different queue claims in this family
- a patient may legitimately need multiple active queue claims on the same day
  when the visit expands across different queues

## When Reuse Is Allowed

Reuse is allowed only when:

- the patient identity matches
- the day matches
- the resolved queue claim matches
- the existing row is active under the canonical active-entry contract

Canonical active statuses for wizard-family reuse:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

## When Multiple Rows Are Allowed

Multiple rows are allowed when:

- the same cart/visit fans out into different `queue_tag` claims
- the patient has different resolved queue claims on the same day

Multiple rows are **not** allowed when:

- the new service still maps to the same resolved queue claim/day for the same
  patient

## Intentional Divergence From Batch Family

Yes, this contract intentionally diverges from the mounted registrar batch-only
family.

Local rule:

- batch-only family -> specialist-level claim
- wizard-family -> queue-tag-level claim

This is acceptable because the two families solve different queue-allocation
problems.

## Compatibility With Global Wave 2C Contracts

This wizard-family contract is compatible with the global contracts because:

- duplicate ownership remains queue-local
- numbering remains queue-local and day-scoped
- fairness still depends on `queue_time` inside each resolved queue claim

## Contract Verdict

Wizard-family should not be migrated as if it were a specialist-level duplicate
family.

Its target contract is queue-tag-level claim ownership with active-row reuse
inside the same resolved queue claim only.
