# Wave 2C Registrar Wizard Behavior Correction

Date: 2026-03-08
Mode: behavior-correction, narrow scope

## Scope

Only the mounted `/registrar/cart` same-day queue-assignment path was corrected.

Changed runtime owner:

- `backend/app/services/morning_assignment.py`

Unchanged:

- numbering algorithm
- `queue_time` semantics
- fairness ordering
- billing / invoice orchestration
- future-day defer behavior
- batch-family behavior
- QR, `OnlineDay`, force-majeure families

## Old Runtime Behavior

The old reuse gate in `MorningAssignmentService._assign_single_queue()`:

- resolved the queue by `queue_tag`
- then reused the first `OnlineQueueEntry` for that concrete queue and patient
- did not explicitly restrict reuse to canonical active statuses
- did not protect against ambiguous same-claim ownership

Practical consequences:

- `diagnostics` and `in_service` were not explicitly part of the contract
- ambiguity inside the same queue-tag claim could be silently flattened
- claim ownership was already queue-tag-driven in practice, but the duplicate gate
  was looser than the target contract

## Corrected Behavior

The corrected duplicate gate now:

- keeps wizard-family claim ownership at `patient_id + queue_tag + queue_day`
- looks for active rows using canonical active statuses only:
  - `waiting`
  - `called`
  - `in_service`
  - `diagnostics`
- reuses one compatible active row if ownership is clear
- does not allocate a new number in that case
- does not change the reused row’s `queue_time`
- raises a safe claim error when same-claim ownership is ambiguous

Inside the mounted `/registrar/cart` flow that ambiguity is handled via the
existing safe failure path:

- no new queue row is created
- no new number is allocated
- `queue_numbers` remains empty for that visit
- the broader billing/cart response shape stays unchanged

## Why Queue-Tag-Level Claim Is Preserved

This correction does **not** collapse wizard-family into batch-family semantics.

Wizard-family still allows:

- multiple active rows for the same specialist/day when `queue_tag` differs
- one visit to expand into multiple queue claims

That remains consistent with:

- `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`
- `docs/architecture/W2C_REGISTRAR_WIZARD_CLAIM_CONTRACT.md`

## Why Same-Queue Duplicates Are Prevented

Inside one resolved queue-tag claim:

- one compatible active row is reused
- more than one compatible active row is treated as ambiguous and unsafe
- no new row is created in the ambiguous case

This aligns the mounted wizard path with:

- `docs/architecture/W2C_ACTIVE_ENTRY_CONTRACT.md`
- `docs/architecture/W2C_DUPLICATE_POLICY_CONTRACT.md`

## Why Different Queue Tags Still Allow Multiple Rows

Different `queue_tag` values remain different queue claims in wizard-family
scope.

So:

- same patient
- same specialist
- same day
- different `queue_tag`

may still legitimately produce multiple active rows.

## Remaining Limitation

The family is still not ready for direct boundary migration because the mounted
`/registrar/cart` runtime owner remains coupled to:

- visit creation
- invoice creation
- invoice-visit linking
- same-day queue assignment
