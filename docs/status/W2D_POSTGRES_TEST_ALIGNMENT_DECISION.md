## Wave 2D Postgres Test Alignment Decision

Date: 2026-03-10
Mode: analysis-first, docs-only

Verdict: `START_WITH_DUAL_VALIDATION_HARNESS`

## Why this is the safest first slice

- The current pytest stack is deeply centered on file-backed SQLite in
  `backend/tests/conftest.py`.
- The highest-value risk sits in queue/concurrency/legacy counter behavior,
  where SQLite/Postgres semantics can diverge.
- A fixture-layer rewrite first would be broader than the current evidence
  justifies.
- A one-sided Postgres pilot would give useful signal, but a dual-validation
  harness makes that signal much easier to trust and debug.

## Why broader migration is not chosen yet

- Full-stack migration would front-load too much fixture churn.
- Queue-sensitive tests already encode SQLite-shaped truths around time,
  transaction visibility, and thread behavior.
- The repo still contains intentional SQLite-only utility tests that should not
  be pulled into the first alignment wave.

## Scope implication

The first code slice should not try to move the whole suite. It should:

1. select one narrow queue-sensitive family
2. prepare it for SQLite-vs-Postgres comparison
3. measure parity/drift explicitly before any broader fixture migration
