# Wave 2C High-Risk Characterization Gaps

Date: 2026-03-07
Mode: analysis-first, docs-only

## Goal

This document identifies what current tests still do not lock down for each
high-risk allocator family.

## Current Coverage Snapshot

Existing useful coverage already present:

- `backend/tests/characterization/test_queue_allocator_characterization.py`
- `backend/tests/characterization/test_queue_allocator_concurrency.py`
- `backend/tests/integration/test_queue_batch_api.py`
- `backend/tests/integration/test_visit_confirmation_api.py`
- `backend/tests/unit/test_visit_confirmation_service.py`
- `backend/tests/integration/test_online_queue_scenarios.py`

## Missing Characterization by Family

### Registrar batch and wizard flows

Current evidence:

- batch endpoint already has tests for source preservation, duplicate detection,
  auto-create queue, and fair numbering

Missing characterization:

- registrar batch with concurrent requests targeting the same specialist queue
- doctor-id to user-id conversion when an existing `DailyQueue` was created with
  the other identity form
- wizard `_create_queue_entries()` numbering behavior when multiple queue tags
  are created in one cart appointment
- wizard confirmation helper replay behavior if the same visit is confirmed
  twice or partially retried
- legacy `create_registrar_appointment()` parity for the count-based same-day
  path

### Confirmation split-flow

Current evidence:

- API tests verify confirmation success and same-day queue creation
- unit tests verify token validation and happy-path confirmation

Missing characterization:

- repeated confirmation replay for a same-day visit
- multi-queue-tag confirmation ordering and numbering
- `doctor.id` vs `user.id` fallback behavior for `visit.doctor_id`
- exact `source`, `status`, and `queue_time` values for newly created entries
- whether duplicate queue rows can be created when confirmation is retried after
  partial failure

### `qr_queue.py` direct SQL allocator branches

Current evidence:

- scenario tests cover QR add-service flows at a high level
- QR join tests cover public join endpoints, not `full_update_online_entry()`

Missing characterization:

- concurrent `full_update_online_entry()` calls targeting the same queue
- direct SQL allocation when additional services branch into a different
  `queue_tag`
- behavior when `DailyQueue` must be auto-created mid-flow
- replay behavior if commit fails after some `flush()` calls
- `all_free` plus paid-invoice path interaction with independent queue entry
  creation

### Force majeure allocator paths

Current evidence:

- one characterization test covers tomorrow-transfer numbering behavior

Missing characterization:

- duplicate prevention if the patient already has an active entry in tomorrow's
  queue
- concurrent transfers into the same tomorrow queue
- exact ordering semantics between inherited priority, new `queue_time`, and
  transferred numbering
- failure path when notification dispatch fails after commit

### `OnlineDay` and other legacy allocator paths

Current evidence:

- legacy path is exercised indirectly by runtime code, but allocator-specific
  characterization is still sparse

Missing characterization:

- phone and Telegram identity replay against `issue_next_ticket()`
- coexistence of `DailyQueue` and `OnlineDay` on the same logical department and
  day
- max-per-day and morning-window behavior under repeated issuance
- parity expectations between `issue_next_ticket()` and `next_ticket_and_insert_entry()`

### Unmounted or duplicate queue entry services

Current evidence:

- boundary tests cover mounted public join flow

Missing characterization:

- whether `online_queue_new_api_service.py` is still reachable through any
  mounted runtime path
- whether `crud/online_queue.py` helpers still back any live endpoint
- payload parity between mounted `online_queue_new.py` and duplicate service
  module responses

## Most Valuable Next Test Pass

The safest missing test pass is:

- confirmation split-flow characterization

Why:

- no direct SQL allocator
- no `OnlineDay` dependency
- current implementation already uses shared queue-service helpers
- missing evidence is mostly about replay and specialist fallback, not a new
  allocator design
