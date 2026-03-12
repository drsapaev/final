## Wave 2D QR Postgres Pilot Plan

Date: 2026-03-11
Mode: pilot-extension, evidence-based

## Target family

- `backend/tests/characterization/test_qr_queue_direct_sql_concurrency.py`

## Why this is the right next bounded pilot family

- It returns to the QR/direct-SQL area, which was historically one of the more
  drift-prone queue-sensitive zones.
- It is bounded, concurrency-oriented, and smaller than broader QR integration
  or queue-time websocket flows.
- It is a good stress check after several stable no-drift pilot runs because it
  still exercises direct-SQL-adjacent behavior.

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
