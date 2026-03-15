## Wave 2D Session Refresh Drift Fix Plan

Date: 2026-03-10
Mode: narrow pilot-fix, evidence-based

## Exact failing pilot tests

Target family:

- `backend/tests/characterization/test_queue_allocator_characterization.py`
- `backend/tests/characterization/test_queue_allocator_concurrency.py`

Observed failing path in the Postgres lane:

- the concurrency family could fail during `_make_concurrency_queue(...)`
- the visible symptom was `InvalidRequestError` around `session.refresh(user)`
- the failure appeared only under `--db-backend=postgres`

## Exact failure mode

Initial symptom:

- `session.refresh(user)` failed under the Postgres pilot lane

Deeper investigation showed:

- the refresh error was only the visible surface
- pooled Postgres sessions were not consistently pinned to the temporary pilot
  schema
- after one threaded pilot test, some later sessions saw the temp schema and
  some fell back to `public`
- this produced inconsistent row visibility and stale identity assumptions

## Why this appears only in the Postgres lane

- the SQLite path uses the existing temp-file database and does not rely on
  Postgres schema routing
- the Postgres pilot path introduces a temporary schema plus pooled
  connections, so search-path consistency matters there

## Candidate root cause

This is not another application schema drift.

The narrow root cause is a pilot harness/session-lifecycle issue:

- the Postgres pilot engine set `search_path` on connect
- that was insufficient for pooled checkout reuse in the threaded pilot family
- the concurrency helper also depended on refresh-after-commit behavior during
  object setup, which made the surface failure noisier than necessary

## Narrowest safe fix strategy

Apply only pilot-scope fixes:

- enforce the temp Postgres schema consistently for the pilot engine
  on startup and on connection checkout
- remove unnecessary `session.refresh(...)` dependence from the concurrency
  helper by using `flush()` and raw ids during setup

## Out of scope

- broad rewrite of `backend/tests/conftest.py`
- migration of the whole test stack to Postgres
- application runtime changes
- unrelated queue logic changes
