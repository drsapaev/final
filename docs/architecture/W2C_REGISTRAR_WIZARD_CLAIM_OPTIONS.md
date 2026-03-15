# Wave 2C Registrar Wizard Claim Options

Date: 2026-03-08
Mode: contract review, docs-only

## Option A: Specialist-Level Claim

Claim key:

- `patient_id + specialist_id + queue_day`

Duplicate implications:

- blocks a second active row for the same specialist/day even if the new service
  maps to a different `queue_tag`

Numbering implications:

- fewer queue rows
- numbering would collapse different queue claims into one specialist-day claim

Fairness implications:

- simple for specialist-day ordering
- weak fit for “new service creates new row with current edit time” semantics

Compatibility with current runtime:

- poor
- runtime expands by `queue_tag`, not by specialist only

Compatibility with batch-family:

- high

Compatibility with morning_assignment:

- low
- `MorningAssignmentService` resolves queues by `queue_tag`

## Option B: Queue-Tag-Level Claim

Claim key:

- `patient_id + resolved_queue_claim + queue_day`

Where `resolved_queue_claim` is the queue identified by `queue_tag` for that
day.

Duplicate implications:

- blocks duplicate active rows only inside the same resolved queue claim
- allows multiple active rows across different `queue_tag` claims

Numbering implications:

- numbering remains queue-local and day-scoped
- aligns with “new service, new queue claim, new current-time placement”

Fairness implications:

- preserves the fairness model per queue
- keeps fresh `queue_time` only for genuinely new queue claims

Compatibility with current runtime:

- high

Compatibility with batch-family:

- intentionally different

Compatibility with morning_assignment:

- high

## Option C: Hybrid Model

Claim key:

- specialist-level by default
- queue-tag-level only for selected tags or resource-queue branches

Duplicate implications:

- harder to explain and harder to verify
- different tags would need exceptions and override rules

Numbering implications:

- mixed semantics across wizard subflows
- likely to increase drift, not reduce it

Fairness implications:

- difficult to reason about because “new service later” could mean either reuse
  or fresh placement depending on tag class

Compatibility with current runtime:

- partial at best

Compatibility with batch-family:

- medium

Compatibility with morning_assignment:

- medium to low

## Chosen Option

For the registrar wizard family, the best target is:

- `Option B: queue-tag-level claim`

## Why Option B Wins

- it matches the design document’s queue-tag-driven placement
- it matches the mounted runtime fan-out behavior
- it aligns with the global queue-local duplicate and numbering contracts better
  than specialist-level collapse would
- it explains why wizard-family may intentionally diverge from batch-family
