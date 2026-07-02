# Wave 2C Test Plan

Date: 2026-03-06
Mode: analysis-first

## Purpose

Queue lifecycle refactor is not safe without a dedicated test matrix.
The current codebase has status drift, mixed read models, and cross-module side effects.

## Test Layers

## 1. Domain Unit Tests

Target:

- future `QueueDomainService`
- queue repositories
- queue status normalization helpers

Required cases:

1. number allocation is monotonic within one queue
2. number allocation respects configured start number
3. duplicate prevention blocks online duplicates for active entries
4. trusted sources (`desk`, `morning_assignment`) bypass duplicate prevention as intended
5. queue position ordering is `priority DESC`, then `queue_time ASC`
6. session id is reused for the same patient + queue + day in active states
7. queue capacity uses the agreed active-state subset

Suggested files:

- `backend/tests/unit/test_queue_domain_service.py`
- `backend/tests/unit/test_queue_repository.py`
- `backend/tests/unit/test_queue_status_aliases.py`

## 2. Transition Matrix Tests

Target:

- canonical queue state machine

Required cases:

1. `waiting -> called`
2. `waiting -> no_show`
3. `called -> no_show`
4. `no_show -> waiting` with elevated priority
5. `cancelled -> waiting` with elevated priority
6. `called -> diagnostics`
7. `in_service -> diagnostics`
8. `called -> incomplete`
9. `diagnostics -> incomplete`
10. invalid transitions are rejected explicitly

Suggested files:

- `backend/tests/integration/test_queue_state_machine.py`

## 3. Visit/Queue Coupling Tests

Target:

- visit status and queue status synchronization

Required cases:

1. canceling a visit marks linked queue row as canceled/cancelled according to migration policy
2. rescheduling a visit marks linked queue row as rescheduled or performs the agreed replacement behavior
3. queue-backed start visit keeps queue and visit lifecycle coherent
4. queue-backed completion keeps queue row and visit row coherent

Suggested files:

- `backend/tests/integration/test_queue_visit_sync.py`

## 4. Read-Model Regression Tests

Target:

- queue position
- queue limits
- queue cabinet info
- reorder status snapshots

Required cases:

1. queue position still reports the same person ahead count
2. queue limit status still counts the same active entries
3. cabinet read endpoints remain unchanged
4. queue snapshot/status endpoints keep stable response shape

Suggested files:

- `backend/tests/integration/test_queue_position_api.py`
- `backend/tests/integration/test_queue_limits_api.py`
- `backend/tests/integration/test_queue_cabinet_api.py`
- `backend/tests/integration/test_queue_snapshot_api.py`

## 5. Side-Effect Tests

Target:

- display websocket notifications
- queue push notifications

Required cases:

1. call-next still emits the expected display event
2. no-show still emits queue refresh/update behavior
3. restore-as-next still emits queue-restored behavior
4. queue-position change still sends the expected notification thresholds

Suggested files:

- `backend/tests/integration/test_queue_notifications.py`

## 6. Concurrency and Idempotency Tests

Target:

- race-prone queue operations

Required cases:

1. concurrent enqueue requests do not allocate the same number
2. repeated call-next does not call the same patient twice
3. repeated cancel/no-show requests are idempotent or fail predictably
4. concurrent restore/reorder operations do not corrupt queue ordering

Suggested files:

- `backend/tests/integration/test_queue_concurrency.py`

## 7. Legacy Parity Tests

Target:

- legacy `OnlineDay` administration still behaves the same until explicitly migrated

Required cases:

1. `appointments.open_day` still opens the legacy queue day
2. `appointments.close_day` still closes the legacy queue day
3. legacy stats still match current counters

Suggested files:

- `backend/tests/integration/test_legacy_online_queue_admin.py`

## Minimum Test Gate for Each Future Wave 2C Slice

For any queue refactor slice:

1. targeted tests for the moved responsibility
2. `cd backend && pytest -q`
3. if router response shapes are touched, add the nearest API integration test

For mutation slices, do not merge without at least:

- one success-path transition test
- one invalid-transition test
- one side-effect assertion or explicit accepted-risk note
