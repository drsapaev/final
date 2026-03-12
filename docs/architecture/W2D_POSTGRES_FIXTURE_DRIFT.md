## Wave 2D Postgres Fixture Drift Analysis

Date: 2026-03-10
Mode: analysis-first, docs-only

## Goal

Document fixture, helper, and test-assumption drift that currently makes the
pytest stack SQLite-friendly.

## 1. File-backed SQLite test engine

Source:

- `backend/tests/conftest.py`

Current behavior:

- temporary `.db` file
- `sqlite:///...`
- `check_same_thread=False`

Drift:

- tuned around SQLite thread limitations rather than Postgres connection
  semantics
- concurrency tests currently treat this setup as the baseline reality

Impact:

- high for queue/concurrency tests

## 2. Savepoint restart pattern on a shared connection

Source:

- `backend/tests/conftest.py`

Current behavior:

- root transaction + nested transaction per test
- event hook restarts savepoint after transaction end

Drift:

- pattern may remain valid on Postgres, but current expectations were shaped
  under SQLite's lightweight file DB and simple connection usage
- tests that open extra sessions/threads can observe different behavior on
  Postgres even if the fixture pattern stays similar

Impact:

- high for characterization and integration tests with concurrent readers

## 3. Missing parity between test engine and app session hardening

Sources:

- `backend/tests/conftest.py`
- `backend/app/db/session.py`

Current behavior:

- app session layer explicitly enables SQLite foreign keys with PRAGMA
- test fixture engine does not mirror that same event-driven enforcement path

Drift:

- test DB behavior is not only different from Postgres, but also not identical
  to the app's own SQLite fallback path

Impact:

- medium to high for FK-sensitive flows

## 4. Naive datetime normalization

Sources:

- `backend/tests/integration/test_online_queue_scenarios.py`
- several queue characterization tests

Current behavior:

- tests repeatedly compare values with `replace(tzinfo=None)`
- comments explicitly say "SQLite stores without timezone"

Drift:

- the suite currently encodes SQLite-specific datetime round-tripping
- Postgres may preserve timezone semantics differently, revealing equality
  assumptions that are not really domain rules

Impact:

- high for queue-time, fairness, and board/stats parity tests

## 5. Concurrency illusions built on thread + file DB behavior

Sources:

- `backend/tests/characterization/test_queue_allocator_concurrency.py`
- `backend/tests/characterization/test_confirmation_split_flow_concurrency.py`
- `backend/tests/characterization/test_registrar_batch_allocator_concurrency.py`

Current behavior:

- Python thread barriers coordinate concurrent read phases
- separate SQLAlchemy sessions bind to the same SQLite file DB

Drift:

- SQLite can under-represent or differently represent locking/isolation behavior
  compared with Postgres
- these tests are valuable, but they are also the clearest place where a
  Postgres pilot may produce different truths

Impact:

- highest

## 6. Scattered local fixtures instead of a centralized factory layer

Sources:

- `backend/tests/conftest.py`
- many queue/integration test modules

Current behavior:

- seed data is often constructed inline
- tests call `commit()` and `refresh()` repeatedly while building fixtures

Drift:

- migration cannot be reduced to one global engine swap
- module-local assumptions about persistence timing may need case-by-case review

Impact:

- medium

## 7. Intentional SQLite-only utility tests

Source:

- `backend/tests/unit/test_migrate_users_to_postgres.py`

Current behavior:

- uses `sqlite3` and `sqlite:///` deliberately

Drift:

- not a bug
- should remain outside the first alignment slice

Impact:

- low for the queue/legacy migration track

## 8. Direct SQL and counter assumptions

Sources:

- queue concurrency characterization files
- QR direct SQL characterization files
- OnlineDay counter characterization files

Current behavior:

- tests assert current truths around raw `MAX(number)+1`, legacy counters,
  duplicated read phases, and split state sources

Drift:

- these are exactly the places where DB engine semantics can matter
- some tests document current runtime drift rather than domain truth, so a
  Postgres pilot must preserve evidence rather than assume failure means the
  test is wrong

Impact:

- high

## Fixture-drift verdict

The current pytest stack has three dominant SQLite-friendly assumptions:

1. file-backed cross-thread SQLite as the canonical test DB
2. naive datetime comparisons shaped by SQLite storage behavior
3. queue/concurrency characterization written against SQLite visibility windows

That makes a full engine swap too risky as a first move. The safest next step
should gather direct SQLite-vs-Postgres evidence on a narrow queue-sensitive
family first.
