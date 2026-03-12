## Scope

Add a narrow `pytest` marker layer for the already validated Postgres pilot
families.

## Files in scope

- [pytest.ini](C:/final/backend/pytest.ini)
- validated pilot families in `backend/tests/characterization/`
- docs/status for marker decision and status

## Marker choice

Chosen single source of truth:

- `@pytest.mark.postgres_pilot`

Why this choice:

- smallest possible implementation
- naturally colocated with the test families it governs
- easy to run locally and in CI with `pytest -m postgres_pilot`
- no extra runner script is required for the first slice

## Initial pilot families included

- allocator characterization / concurrency
- open_close characterization
- queues.stats parity harness
- board_state parity harness
- force_majeure allocator characterization
- confirmation split-flow concurrency
- registrar batch allocator concurrency
- qr_queue direct-SQL concurrency
- qr_queue direct-SQL characterization

## Safety

- SQLite remains the default lane
- Postgres remains opt-in through `--db-backend=postgres`
- no runtime behavior changes
- no fixture architecture rewrite

## Out of scope

- CI workflow wiring
- PR vs nightly split
- broad test infra migration
- adding more candidate families beyond the already validated set
