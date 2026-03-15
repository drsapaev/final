## Wave 2D Postgres Test Migration Options

Date: 2026-03-10
Mode: analysis-first, docs-only

## Option A: full-stack migration later, no early pilot

Meaning:

- keep current SQLite harness as-is until there is enough time to rework the
  full fixture layer in one broader effort

Pros:

- no short-term complexity
- avoids partial infra branching

Risks:

- keeps the current confidence gap in place
- delays discovery of queue/concurrency drift
- makes later migration larger and harder to debug

Migration effort:

- high, delayed

Confidence gain:

- low until the broader effort begins

Rollback simplicity:

- high now, low later because the delayed change becomes broader

## Option B: small pilot subset of queue-sensitive tests on Postgres

Meaning:

- introduce a narrow Postgres-backed path for a selected queue-sensitive family
- keep the main suite on SQLite for now

Pros:

- targets the highest-risk domain first
- gives real production-aligned signal quickly
- avoids rewriting the whole stack

Risks:

- may be hard to interpret failures without an explicit SQLite-vs-Postgres
  comparison layer
- can tempt ad hoc fixture branching if not scoped carefully

Migration effort:

- medium

Confidence gain:

- high

Rollback simplicity:

- good, if the pilot is isolated

## Option C: dual-path validation harness first

Meaning:

- prepare one narrow family so it can be exercised against both the current
  SQLite harness and a Postgres-backed path
- use the harness to measure drift before deciding whether to expand migration

Pros:

- highest evidence quality before changing defaults
- makes failures interpretable instead of surprising
- preserves the current suite while adding a controlled confidence lane

Risks:

- requires a small amount of infrastructure work before it yields value
- slightly slower than a one-sided pilot

Migration effort:

- medium

Confidence gain:

- highest

Rollback simplicity:

- highest among meaningful next steps

## Option D: fixture-layer refactor first, then pilot

Meaning:

- refactor `conftest.py` and fixture ownership before any Postgres-backed pilot

Pros:

- can reduce long-term duplication if done well

Risks:

- refactors infra before we have enough empirical drift evidence
- increases blast radius immediately
- likely touches many tests before we know which families need it most

Migration effort:

- high

Confidence gain:

- medium

Rollback simplicity:

- lower than a harness-first approach

## Option comparison verdict

The safest first move is Option C: dual-path validation harness first.

Reason:

- it maximizes evidence with the smallest irreversible change
- it avoids a blind fixture refactor
- it keeps the current SQLite suite intact while probing the exact queue/legacy
  families most likely to drift on Postgres
