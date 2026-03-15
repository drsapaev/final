## Wave 2D Registrar Batch Postgres Pilot Plan

Date: 2026-03-11
Mode: pilot-extension, evidence-based

## Target family

- `backend/tests/characterization/test_registrar_batch_allocator_concurrency.py`

## Why this is the right next bounded pilot family

- It is another bounded concurrency-sensitive queue family after the already
  stable confirmation split-flow concurrency pilot.
- It exercises duplicate-read behavior in the registrar batch area, which is a
  realistic place for SQLite/Postgres transaction-visibility drift to surface.
- It remains smaller and lower-risk than broader queue integration families.

## Reused dual-lane harness parts

- default SQLite lane remains unchanged
- opt-in Postgres lane via `--db-backend=postgres`
- isolated temporary Postgres schema
- existing search-path enforcement for pooled Postgres connections

## Narrow additions needed

None planned up front.

Strategy:

- run the family in SQLite
- run the same family in Postgres
- only add a narrow harness adjustment if the family exposes a real blocker

## Out of scope

- broad fixture rewrite
- full test-stack migration to Postgres
- application/runtime changes
- unrelated queue-sensitive families
