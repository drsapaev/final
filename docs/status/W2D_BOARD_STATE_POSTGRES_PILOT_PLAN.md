## Wave 2D Board State Postgres Pilot Plan

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Target family

- `backend/tests/characterization/test_board_state_parity_harness.py`

## Why this is the right next pilot family

- It stays close to the same OnlineDay/legacy read-model area as the already
  piloted `queues.stats` family.
- It verifies legacy-vs-adapter parity rather than allocator or concurrency
  behavior, so it broadens the pilot evidence without broadening infrastructure.
- It is characterization-oriented and bounded, which makes it a safe next
  extension.

## Reused dual-lane harness parts

- default SQLite lane remains unchanged
- opt-in Postgres lane via `--db-backend=postgres`
- isolated temporary Postgres schema
- existing schema/search-path pinning for the Postgres pilot path

## Narrow additions needed

None planned up front.

Strategy:

- run the family in SQLite
- run the same family in Postgres
- only add a narrow harness adjustment if the family surfaces real DB drift or
  a pilot-lane issue

## Out of scope

- broad fixture rewrite
- full test-stack migration to Postgres
- application/runtime changes
- unrelated queue-sensitive families
