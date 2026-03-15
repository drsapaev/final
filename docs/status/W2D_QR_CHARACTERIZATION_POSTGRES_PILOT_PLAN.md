## Wave 2D QR Characterization Postgres Pilot Plan

Date: 2026-03-11
Mode: pilot-extension, evidence-based

## Target family

- `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`

## Why this is the right next bounded pilot family

- It stays inside the already-bounded QR direct-SQL area, but exercises
  characterization behavior rather than only concurrency windows.
- It is historically sensitive because it mixes QR flows, raw next-number
  behavior, and service setup details in one narrow family.
- It is still much safer than broad queue integration or fixture migration.

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
- only classify the surfaced blocker if a real DB-lane drift appears

## Out of scope

- broad fixture rewrite
- full test-stack migration to Postgres
- application/runtime changes
- unrelated queue-sensitive families
