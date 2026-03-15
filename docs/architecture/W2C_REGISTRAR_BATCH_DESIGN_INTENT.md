# Wave 2C Registrar Batch Design Intent

Date: 2026-03-08
Mode: analysis-first, docs-only

## Evidence Used

- `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`
- `docs/architecture/W2C_DUPLICATE_POLICY_CONTRACT.md`
- `docs/architecture/W2C_ACTIVE_ENTRY_CONTRACT.md`
- `docs/architecture/W2C_QUEUE_NUMBERING_CONTRACT.md`
- `docs/architecture/W2C_REGISTRAR_BATCH_TRACE.md`
- `docs/architecture/W2C_REGISTRAR_BATCH_POLICY_COUPLING.md`
- mounted runtime comments in `backend/app/api/v1/endpoints/registrar_integration.py`
- existing service seam in `backend/app/services/queue_batch_service.py`

## Scope

This document clarifies intent only for the narrow registrar batch-only family:

- `POST /api/v1/registrar-integration/queue/entries/batch`
- add-new-services flow for desk/admin edit mode

It does **not** redefine:

- QR full-update behavior
- confirmation flow
- legacy `OnlineDay`
- full registrar wizard family

## Reading Of The Design Sources

The design document establishes two important principles:

1. one patient may have multiple queue entries across the same day
2. hybrid edit mode creates new queue entries for **new services**

However, the same evidence set is more specific about the registrar batch-only
family:

- mounted runtime says duplicate prevention is "patient already in queue to
  specialist today"
- mounted runtime groups by `specialist_id`
- unmounted `QueueBatchService` preserves that same specialist-level grouping
- existing integration and characterization tests also treat specialist-level
  grouping as current intended batch behavior

This means the broad queue design must be narrowed for this subfamily instead
of copied mechanically from QR/service-level flows.

## Answers

### 1. Should `diagnostics` count as active for registrar batch duplicate gate?

Yes.

Reasoning:

- the canonical active-entry contract already treats `diagnostics` as active
- registrar batch-only flow should not create a second live queue claim for the
  same batch claim while the first claim is still in progress
- hybrid edit mode preserves existing queue ownership and only adds new claims
  when the patient is not already occupying that same batch claim

For this subfamily, `diagnostics` must block a new allocation in the same
claim.

### 2. Are multiple active queue rows allowed for one patient/day under the same `specialist_id`?

No, not in the registrar batch-only contract.

Reasoning:

- mounted runtime defines duplicate intent as "already in queue to specialist
  today"
- `QueueBatchService` keeps the same grouping rule
- batch-only flow is a narrow add-services helper, not a general queue-claim
  redesign path

Multiple active rows remain allowed across different claims, but not for the
same batch claim.

### 3. Is registrar batch queue claim doctor-level or service-level?

For this family, the target claim is **specialist-level**.

More precisely:

- day-scoped
- patient-scoped
- specialist-user scoped

It is **not** service-level for this family.

That does **not** mean all queue families are specialist-level. QR full-update
and other queue paths can still use finer-grained queue-tag behavior. This
decision is intentionally local to registrar batch-only flow.

## Resulting Intent Statement

Registrar batch-only flow should be read as:

"If the patient already has an active queue claim for this specialist today,
reuse that claim instead of creating another row. Only create a new row when
the patient does not already have an active claim for that specialist/day."

## Implication

The current ambiguity is resolved enough to move from contract clarification to
a narrow behavior-correction slice.
