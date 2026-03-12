## Wave 2D Queue Postgres Harness Plan

Date: 2026-03-10
Mode: pilot-first, bounded

## Target pilot tests

- `backend/tests/characterization/test_queue_allocator_characterization.py`
- `backend/tests/characterization/test_queue_allocator_concurrency.py`

## Safety goals

- keep the current SQLite default path intact
- introduce a clearly opt-in Postgres lane only for pilot execution
- avoid broad fixture rewrites
- avoid any application runtime behavior changes

## Minimal fixture/config layer

Planned harness shape:

- add an opt-in pytest switch: `--db-backend=postgres`
- preserve default `sqlite` backend when the switch is not used
- for the Postgres path, provision a temporary isolated schema inside the
  existing Postgres database
- reuse the current test family unchanged as much as possible

## Why this is safe

- default test commands still hit the same SQLite path
- Postgres path is explicit, isolated, and pilot-only
- no route/runtime behavior is touched
- no broad `conftest.py` redesign is introduced

## Explicitly out of scope

- switching the whole suite to Postgres
- rewriting all fixtures/factories
- refactoring unrelated test families
- changing queue semantics or application behavior
