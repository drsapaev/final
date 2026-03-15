## Next Execution Unit After Postgres Test Prep

Date: 2026-03-10
Mode: analysis-first, docs-only

## Chosen first slice

Dual validation harness for one queue-sensitive family.

## Exact first execution unit

Start with:

- `backend/tests/characterization/test_queue_allocator_characterization.py`
- `backend/tests/characterization/test_queue_allocator_concurrency.py`

## Why this family first

- It sits closest to the core queue allocator behavior already refactored in
  Wave 2C.
- It combines the two highest-risk drift categories:
  - allocator/duplicate logic
  - concurrent read-phase behavior
- It is narrow enough to pilot without rewriting the whole fixture stack.

## What the slice should do

1. prepare a Postgres-capable test harness path isolated from the default SQLite
   suite
2. run the selected allocator characterization family against both backends
3. document strict parity, acceptable mismatch categories, and true DB-semantic
   drift

## Why not a broader slice yet

- Queue-time timezone assertions and OnlineDay legacy counters should follow
  after a first pilot proves the harness approach is workable.
- Refactoring the global fixture layer before a pilot would be broader and less
  evidence-driven.
