## Wave 2D Confirmation Postgres Pilot Plan

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Target family

- `backend/tests/characterization/test_confirmation_split_flow_concurrency.py`

## Why this is the right next bounded pilot family

- It returns to a bounded concurrency-sensitive family after several stable
  no-drift pilot runs.
- It exercises confirmation-token validation and pending-visit lookup under
  concurrent reads, which is exactly the kind of session/visibility behavior
  where SQLite/Postgres differences can matter.
- It remains smaller and lower-risk than broader queue integration families.

## Reused dual-lane harness parts

- default SQLite lane remains unchanged
- opt-in Postgres lane via `--db-backend=postgres`
- isolated temporary Postgres schema
- existing schema/search-path enforcement for pooled Postgres connections

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
