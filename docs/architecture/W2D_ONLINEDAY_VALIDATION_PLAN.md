# Wave 2D OnlineDay Validation Plan

Date: 2026-03-09
Mode: analysis-first, docs-only

## Validation goals before deprecation

Before any OnlineDay cleanup/removal work, validation must prove:

1. mounted legacy endpoints still behave as documented
2. replacement or retirement work does not break operator-facing behavior
3. board/stats visibility remains available where required
4. legacy numbering/state transitions are understood well enough to retire
   safely

## Required validation buckets

### 1. Endpoint characterization baseline

Needed for:

- `appointments.open_day()`
- `appointments.stats()`
- `appointments.close_day()`
- `queues.stats()`
- `queues.next_ticket()`
- `board.state()`

Checks:

- request/response shape
- auth/role expectations
- open/close state transitions
- stats payload values
- ticket issuing side effects

### 2. Numbering and state validation

Needed for:

- `queues.next_ticket()`
- `online_queue.issue_next_ticket()`
- `load_stats()`

Checks:

- `start_number` handling
- `last_ticket` increment behavior
- waiting counter increments
- serving/done counters remain stable unless explicitly changed elsewhere

### 3. Board / stats compatibility validation

Needed for:

- `appointments.stats()`
- `queues.stats()`
- `board.state()`

Checks:

- same department/day inputs produce consistent visible counters
- board payload remains usable for current consumers
- stats endpoints are characterized before deciding retire-vs-replace

### 4. Cleanup safety checks for dead/support surfaces

Needed for:

- disabled routers
- support-only mirrors
- stale helpers

Checks:

- import/reference audit
- route registry confirmation
- smoke check that mounted runtime still behaves the same after cleanup

### 5. Rollback considerations

Cleanup phases must be reversible until final removal:

- no early schema deletion
- keep `OnlineDay` model/service in place until live mounted endpoints are gone
- cleanup PRs should be phase-scoped so rollback can restore a narrow slice

## Environment note

Because the project runtime uses PostgreSQL while the pytest harness still uses
SQLite, final removal/replacement work should not rely on SQLite-only signal.

For later execution phases, add:

- pytest characterization coverage
- mounted endpoint smoke checks
- targeted Postgres-aligned verification for legacy counter behavior

## Validation-plan verdict

The first execution slices after this prep should focus on low-risk cleanup
only. Live OnlineDay removal must wait for:

- endpoint characterization
- consumer mapping
- replacement/retirement decision
- rollback-ready phased execution
