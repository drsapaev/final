## Wave 2D Force Majeure Postgres Pilot Plan

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Target family

- `backend/tests/characterization/test_force_majeure_allocator_characterization.py`

## Why this is the right next bounded pilot family

- It remains queue/legacy-sensitive, but inside the isolated exceptional-domain
  rather than the main queue allocator path.
- It already exposed source semantics in earlier drift work, so it is a useful
  bounded follow-up under the Postgres pilot.
- It is small, characterization-oriented, and does not require broad fixture
  movement.

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
