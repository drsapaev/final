## Wave 2D Postgres Test Infra Inventory

Date: 2026-03-10
Mode: analysis-first, docs-only

## Goal

Capture where the backend test stack still depends on SQLite-oriented behavior,
even though runtime development and production are already Postgres-oriented.

## Current baseline

- Runtime/dev DB target: Postgres via `backend/.env`
- Pytest DB target: file-backed SQLite via `backend/tests/conftest.py`

## Relevant layers

### 1. Global pytest DB bootstrap

- File: `backend/tests/conftest.py`
- Layer: `test_db` fixture
- Current DB assumption:
  - creates a temporary file-backed SQLite database
  - uses `create_engine("sqlite:///...")`
  - enables `check_same_thread=False` because `TestClient` and thread-based tests
    need a shared file DB
- SQLite-specific: yes
- Likely Postgres drift risk: high
- Migration complexity: high
- Notes:
  - this is the single most important infra layer
  - comments explicitly document that in-memory SQLite was rejected because of
    thread behavior

### 2. Per-test transaction isolation

- File: `backend/tests/conftest.py`
- Layer: `db_session` fixture
- Current DB assumption:
  - single shared connection per test
  - root transaction + `begin_nested()` savepoint restart pattern
- SQLite-specific: partially
- Likely Postgres drift risk: high
- Migration complexity: high
- Notes:
  - nested-savepoint restart pattern is generic SQLAlchemy, but current usage is
    tuned around the SQLite test engine and its threading model
  - visibility/locking behavior under Postgres may differ for queue/concurrency
    tests

### 3. API client fixture

- File: `backend/tests/conftest.py`
- Layer: `client` fixture
- Current DB assumption:
  - FastAPI dependency override yields the same SQLAlchemy session created from
    the SQLite-backed fixture
- SQLite-specific: indirectly yes
- Likely Postgres drift risk: medium
- Migration complexity: medium
- Notes:
  - most API integration tests inherit DB semantics from this fixture

### 4. Pytest configuration

- File: `backend/pytest.ini`
- Layer: test discovery / marker config
- Current DB assumption: none directly
- SQLite-specific: no
- Likely Postgres drift risk: low
- Migration complexity: low
- Notes:
  - config itself is neutral; the drift lives in fixture and helper layers

### 5. App session layer used outside fixture override

- File: `backend/app/db/session.py`
- Layer: application DB engine/session owner
- Current DB assumption:
  - runtime prefers `DATABASE_URL`
  - falls back to SQLite only if config/env does not provide a DB URL
  - SQLite path has explicit `check_same_thread=False` and `PRAGMA foreign_keys`
- SQLite-specific: mixed
- Likely Postgres drift risk: medium
- Migration complexity: medium
- Notes:
  - most tests bypass this with `get_db` override
  - some smoke/integration tests instantiate `app` directly and should still be
    reviewed for hidden runtime-engine assumptions

### 6. Runtime settings baseline

- File: `backend/.env`
- Layer: dev/runtime configuration
- Current DB assumption: Postgres (`postgresql+psycopg://...`)
- SQLite-specific: no
- Likely Postgres drift risk: none
- Migration complexity: none
- Notes:
  - this confirms the architectural mismatch: runtime is already Postgres-first
    while pytest remains SQLite-first

### 7. Intentional SQLite-only migration tests

- File: `backend/tests/unit/test_migrate_users_to_postgres.py`
- Layer: migration utility tests
- Current DB assumption:
  - uses `sqlite3` and `sqlite:///` on purpose to validate migration scripts
- SQLite-specific: yes, by design
- Likely Postgres drift risk: low for the main queue track
- Migration complexity: none for first alignment wave
- Notes:
  - should remain out of the first Postgres-alignment pilot

### 8. Distributed fixture ownership inside test modules

- Files:
  - `backend/tests/integration/test_online_queue_scenarios.py`
  - `backend/tests/integration/test_queue_batch_api.py`
  - `backend/tests/characterization/*queue*`
  - many other test modules with local fixtures
- Layer: per-module fixtures and seed helpers
- Current DB assumption:
  - many module-local fixtures commit/refresh aggressively and assume the global
    SQLite harness underneath
- SQLite-specific: indirectly yes
- Likely Postgres drift risk: medium to high
- Migration complexity: medium
- Notes:
  - there is no centralized factory layer for queue/legacy test data
  - migration will need staged fixture review, not only one global engine swap

## Inventory verdict

The current test stack is structurally centered on file-backed SQLite. The
highest-risk migration points are:

1. `backend/tests/conftest.py` engine/session lifecycle
2. queue/concurrency characterization tests using multiple sessions/threads
3. time and timezone assertions that currently normalize to SQLite-friendly
   naive datetimes
