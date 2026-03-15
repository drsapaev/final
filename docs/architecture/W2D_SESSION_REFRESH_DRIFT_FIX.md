## Wave 2D Session Refresh Drift Fix

Date: 2026-03-10
Mode: narrow pilot-fix, evidence-based

## Exact issue

The remaining Postgres-lane blocker in the queue allocator pilot family first
appeared as:

- `InvalidRequestError` on `session.refresh(user)`

The failure surfaced during setup inside:

- `backend/tests/characterization/test_queue_allocator_concurrency.py`

## What the issue really was

The root cause was not another application-level schema drift.

It was a narrow pilot harness/session-lifecycle issue:

- the Postgres pilot path created a temporary schema
- `search_path` was applied on initial connection
- pooled connections reused later by the threaded pilot family were not always
  pinned back to that temp schema
- this produced inconsistent visibility across sessions and made setup objects
  appear stale or missing

So the visible `refresh(user)` error was a symptom, not the true contract
problem.

## Exact narrow fix applied

### 1. Pilot schema routing hardening

In `backend/tests/conftest.py` the opt-in Postgres pilot engine now enforces the
temporary schema through:

- startup `connect_args={"options": "-csearch_path=..."}`
- an engine `connect` hook
- an engine `checkout` hook

This keeps the fix local to the pilot lane.

### 2. Concurrency helper stabilization

In `backend/tests/characterization/test_queue_allocator_concurrency.py` the
setup helper no longer relies on `session.refresh(...)` after commit.

Instead it:

- adds objects
- uses `flush()` to capture ids
- returns raw ids/tags needed by the test threads

This avoids unnecessary identity reload dependence in the pilot setup path.

## Why this is the narrowest honest fix

- no application runtime behavior changed
- no queue logic changed
- no broad fixture architecture rewrite was introduced
- no failures were hidden by weakening assertions
- the fix stays local to the pilot harness and target family

## Result

After the fix:

- SQLite pilot family passes: `7 passed`
- Postgres pilot family passes: `7 passed`

This means the remaining blocker in the target family was a
harness/session-lifecycle issue, not another unresolved queue-domain drift.
