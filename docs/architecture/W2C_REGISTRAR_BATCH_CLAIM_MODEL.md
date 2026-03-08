# Wave 2C Registrar Batch Claim Model

Date: 2026-03-08
Mode: analysis-first, docs-only

## Options Considered

### Option A — Specialist-level claim

One active queue claim per:

- patient
- specialist
- day

Pros:

- matches mounted runtime grouping
- matches existing `QueueBatchService`
- matches current integration and characterization tests
- matches endpoint comment "already in queue to specialist today"

Cons:

- narrower than the broadest reading of "new service creates new queue entry"

### Option B — Service-level claim

One active queue claim per:

- patient
- service
- day

Pros:

- aligns with the broadest interpretation of "one entry per service/specialist"

Cons:

- conflicts with mounted runtime
- conflicts with current service seam
- would require queue claim resolution the batch family does not currently own
- would turn this narrow track into a broader registrar redesign

### Option C — Hybrid / queue-tag-based claim

One active queue claim per:

- patient
- derived queue claim (`queue_tag` / queue profile)
- day

Pros:

- closer to global queue architecture
- aligns better with QR full-update wording

Cons:

- not how the mounted registrar batch path works today
- `DailyQueue` is auto-created with `queue_tag=None` in this family
- current batch request handling never derives a stable queue-tag claim

## Chosen Target Model

For registrar batch-only flow, the target model is:

`Option A — specialist-level claim`

## Why This Is The Right Local Choice

This target minimizes drift while still aligning with the broader queue
contracts:

- it preserves current specialist-day grouping already present in runtime
- it uses the already existing mounted and unmounted batch seam
- it avoids silently importing QR-specific queue-tag semantics into registrar
  batch flow
- it still allows multiple active rows across different specialists on the same
  day

## Important Boundary

This decision is local to the registrar batch-only family.

It does **not** redefine:

- QR full-update claim model
- confirmation flow claim model
- future queue-tag-aware refactors outside this subfamily

## Contract Statement

Registrar batch-only queue claim is:

`patient_id + specialist_user_id + queue_day`

Service selection expands the business context of that claim, but does not
create a second active claim for the same specialist/day.
