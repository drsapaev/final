## Wave 2D Postgres-Sensitive Tests

Date: 2026-03-10
Mode: analysis-first, docs-only

## Goal

Identify which tests are most likely to behave differently once a Postgres-backed
test path is introduced.

## Priority 1: queue allocator and duplicate/concurrency characterization

### Files

- `backend/tests/characterization/test_queue_allocator_characterization.py`
- `backend/tests/characterization/test_queue_allocator_concurrency.py`
- `backend/tests/characterization/test_confirmation_split_flow_concurrency.py`
- `backend/tests/characterization/test_registrar_batch_allocator_concurrency.py`
- `backend/tests/characterization/test_qr_queue_direct_sql_concurrency.py`

### Why sensitive

- They model read-before-write races, duplicate checks, and `MAX(number)+1`
  allocation patterns.
- They intentionally use multiple sessions and Python threads against the same
  temporary database.
- Postgres locking and transaction visibility can differ materially from
  SQLite's file-backed behavior.

### Likely drift type

- different visibility windows for duplicate detection
- different next-number race behavior
- different read-phase outcomes under concurrent sessions

### Migration priority

- highest

## Priority 2: queue and legacy counter operational characterization

### Files

- `backend/tests/characterization/test_open_close_day_characterization.py`
- `backend/tests/characterization/test_queues_stats_parity_harness.py`
- `backend/tests/characterization/test_board_state_parity_harness.py`
- `backend/tests/characterization/test_force_majeure_allocator_characterization.py`

### Why sensitive

- These tests assert behavior that joins legacy `Setting(category="queue")`,
  `OnlineDay`, and queue snapshots.
- Postgres alignment matters because these flows combine updates, reads, and
  response snapshots across multiple state sources.

### Likely drift type

- commit visibility differences
- ordering/timestamp differences
- stronger FK / transactional consistency surfacing hidden drift sooner

### Migration priority

- high

### Pilot status update

- `backend/tests/characterization/test_open_close_day_characterization.py`
  has now been exercised successfully in both the default SQLite lane and the
  opt-in Postgres lane.
- No SQLite-vs-Postgres drift was observed for this family in the current pilot
  harness.
- This makes it a confirmed stable second-family pilot rather than only a
  predicted sensitive area.
- `backend/tests/characterization/test_queues_stats_parity_harness.py`
  has now also been exercised successfully in both lanes.
- No DB-specific drift was observed there either; strict parity and documented
  compatibility-only mismatches behaved the same under SQLite and Postgres.
- `backend/tests/characterization/test_board_state_parity_harness.py`
  has now also been exercised successfully in both lanes.
- No DB-specific drift was observed there either; queue parity and
  compatibility parity remained stable under SQLite and Postgres.
- `backend/tests/characterization/test_force_majeure_allocator_characterization.py`
  has now also been exercised successfully in both lanes.
- No DB-specific drift was observed there either; the isolated
  exceptional-domain characterization stayed stable under SQLite and Postgres.
- `backend/tests/characterization/test_confirmation_split_flow_concurrency.py`
  has now also been exercised successfully in both lanes.
- No DB-specific drift was observed there either; bounded confirmation
  read-phase concurrency behavior remained stable under SQLite and Postgres.
- `backend/tests/characterization/test_registrar_batch_allocator_concurrency.py`
  has now also been exercised successfully in both lanes.
- No DB-specific drift was observed there either; bounded registrar-batch
  duplicate-read concurrency behavior remained stable under SQLite and Postgres.
- `backend/tests/characterization/test_qr_queue_direct_sql_concurrency.py`
  has now also been exercised successfully in both lanes.
- No DB-specific drift was observed there either; bounded QR direct-SQL
  concurrency behavior remained stable under SQLite and Postgres.
- `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`
  has now also been exercised in both lanes.
- That family surfaced a real bounded schema drift under Postgres:
  `Service.service_code` length enforcement rejects values that SQLite accepted
  during QR characterization setup.

## Priority 3: queue-time and timezone-sensitive integration flows

### Files

- `backend/tests/integration/test_online_queue_scenarios.py`
- `backend/tests/integration/test_online_queue_new_join.py`
- `backend/tests/integration/test_qr_queue_join.py`
- `backend/tests/integration/test_queue_time_websocket_e2e.py`

### Why sensitive

- These tests explicitly compare timezone-aware inputs to naive values because
  SQLite stores datetimes without timezone metadata in the current harness.
- Queue ordering, fairness, and `opened_at` semantics are time-sensitive.

### Likely drift type

- timezone-awareness differences
- serialization/round-trip changes
- datetime equality expectations no longer matching Postgres behavior

### Migration priority

- high

## Priority 4: queue API integration flows using shared session/client fixture

### Files

- `backend/tests/integration/test_queue_batch_api.py`
- `backend/tests/integration/test_context_facade_pilot_flows.py`
- `backend/tests/integration/test_visit_confirmation_api.py`
- queue-oriented unit tests around `queue_domain_service`, `queue_*_api_service`,
  and `queues_stats_replacement`

### Why sensitive

- They rely on the global `client` + `db_session` fixture path.
- They are less concurrency-focused than characterization tests, but still
  depend on duplicate checks, numbering, and queue-time persistence.

### Likely drift type

- transaction scope / flush/commit timing
- FK enforcement and relationship persistence
- datetime round-trip expectations

### Migration priority

- medium

## Priority 5: non-queue DB-dependent tests

### Files

- `backend/tests/integration/test_rbac_matrix.py`
- selected payment and audit integration tests

### Why sensitive

- They depend on DB lifecycle and commit visibility, but are not the main source
  of SQLite/Postgres architectural risk for the post-W2C tail.

### Likely drift type

- FK/constraint enforcement
- transaction scope

### Migration priority

- lower than queue/legacy flows

## Explicitly out of the first alignment wave

### Files

- `backend/tests/unit/test_migrate_users_to_postgres.py`

### Why

- This test intentionally uses SQLite as a migration source/target model and is
  not evidence of production queue behavior drift.

## Sensitive-area verdict

The first Postgres-aligned slice should focus on queue-sensitive
characterization/integration families, especially:

1. allocator characterization
2. allocator concurrency
3. OnlineDay legacy operational characterization
4. timezone-sensitive queue flows
