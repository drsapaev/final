## Wave 2D Queues Stats Postgres Pilot Plan

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Target family

- `backend/tests/characterization/test_queues_stats_parity_harness.py`

## Why this is the right next pilot family

- It stays inside the OnlineDay/legacy stats area that is already known to be
  DB-sensitive.
- It compares legacy counters with the SSOT-backed replacement direction,
  making it a good next signal after allocator and open/close pilot families.
- It is narrow, deterministic, and lower-risk than broader queue integration
  families.

## Reused dual-lane harness parts

- default SQLite lane remains unchanged
- opt-in Postgres lane via `--db-backend=postgres`
- isolated temporary Postgres schema
- existing schema/search-path pinning for pooled Postgres connections

## Narrow additions needed

None planned up front.

Strategy:

- run the family in SQLite
- run the same family in Postgres
- only add a narrow harness adjustment if the family reveals real drift or a
  pilot-lane issue

## Out of scope

- broad fixture rewrite
- full test-stack migration to Postgres
- application runtime changes
- unrelated queue-sensitive families
