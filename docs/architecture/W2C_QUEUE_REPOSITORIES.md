# Wave 2C Queue Repository Boundaries

Date: 2026-03-06
Mode: analysis-first

## Current Situation

The backend already contains queue-specific repositories, but they are route-oriented, not domain-oriented:

- `queue_api_repository.py`
- `queue_batch_repository.py`
- `queue_reorder_api_repository.py`
- `queue_position_api_repository.py`
- `queue_limits_repository.py`
- `online_queue_new_repository.py`
- `qr_queue_api_repository.py`

These repositories are useful, but they do not define one stable queue lifecycle boundary.

## Target Repository Set

Wave 2C should converge on a smaller set of domain-facing repositories.

## QueueRepository

`QueueRepository` should own all queue persistence needed by `QueueDomainService`.

Suggested responsibilities:

- fetch one daily queue
- create one daily queue
- lock queue for number allocation if needed
- compute next queue number
- fetch one queue entry
- fetch one queue entry by visit id
- fetch active entries for a queue
- fetch next callable entry
- count active entries
- find duplicate active entry for patient, phone, or telegram id
- persist entry status changes
- persist priority changes
- persist queue metadata changes related to queue lifecycle

Suggested interface:

```python
class QueueRepository:
    def get_daily_queue(self, *, day: date, specialist_id: int, queue_tag: str | None = None) -> DailyQueue | None: ...
    def create_daily_queue(self, *, day: date, specialist_id: int, queue_tag: str | None, defaults: dict[str, Any] | None = None) -> DailyQueue: ...
    def get_entry(self, *, entry_id: int) -> OnlineQueueEntry | None: ...
    def get_entry_by_visit(self, *, visit_id: int) -> OnlineQueueEntry | None: ...
    def list_active_entries(self, *, queue_id: int, active_statuses: list[str]) -> list[OnlineQueueEntry]: ...
    def get_next_waiting_entry(self, *, queue_id: int) -> OnlineQueueEntry | None: ...
    def count_active_entries(self, *, queue_id: int, active_statuses: list[str]) -> int: ...
    def find_duplicate_entry(
        self,
        *,
        queue_id: int,
        patient_id: int | None,
        phone: str | None,
        telegram_id: int | None,
        active_statuses: list[str],
    ) -> OnlineQueueEntry | None: ...
    def get_next_number(self, *, queue_id: int, default_start: int) -> int: ...
    def save(self, obj: Any) -> None: ...
    def flush(self) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

## VisitRepository

`VisitRepository` should be used by `QueueDomainService` only for queue-coupled visit operations.

Suggested responsibilities:

- fetch visit by id
- update visit status or finish/start timestamps
- update visit date during reschedule
- create or fetch queue-driven visit when needed

Suggested interface:

```python
class VisitRepository:
    def get_visit(self, *, visit_id: int) -> Visit | None: ...
    def set_visit_status(self, *, visit_id: int, status: str) -> Visit: ...
    def set_visit_date(self, *, visit_id: int, new_day: date) -> Visit: ...
    def find_or_create_today_visit(
        self,
        *,
        patient_id: int,
        doctor_id: int | None,
        department: str | None,
    ) -> Visit: ...
```

## Optional Supporting Repositories

These can remain separate because they are read-model or catalog boundaries:

- `QueueProfileRepository`
- `QueueReadRepository`
- `QueueNotificationOutboxRepository`

Wave 2C does not need to introduce them immediately if the existing services already cover those reads.

## Boundary Rules

### Router layer

- may validate request input
- may resolve auth/role dependencies
- may call application or domain service
- must not perform raw queue ORM mutation

### QueueDomainService

- may combine `QueueRepository` and `VisitRepository`
- owns queue transition validation
- owns active-status policy
- owns commit ordering

### Repositories

- perform persistence only
- do not contain HTTP concerns
- do not decide business policy such as which transitions are allowed

## Transaction Strategy

Wave 2C does not require a new framework.

Minimal acceptable strategy:

- one SQLAlchemy session per request
- service owns the unit-of-work boundary
- repositories share that session
- side effects happen after successful commit

## First Repository Extraction Targets

Most realistic first boundaries:

1. `QueueRepository.get_next_number`
2. `QueueRepository.find_duplicate_entry`
3. `QueueRepository.get_next_waiting_entry`
4. `QueueRepository.list_active_entries`
5. `VisitRepository.get_visit` and `set_visit_date`

These cover the queue invariants with the least architectural risk.

## Phase 1 Implementation Status

Wave 2C Phase 1 introduced `QueueReadRepository` in
`backend/app/repositories/queue_read_repository.py`.

Current implemented read boundary:

- `get_queue(queue_id)`
- `list_active_doctors(specialty)`
- `get_queue_by_specialist_day(specialist_id, day)`
- `list_daily_queues(day_obj, specialist_id, cabinet_number)`
- `get_doctor(doctor_id)`
- `count_entries(queue_id)`
- `list_snapshot_entries(queue_id, statuses)`

This repository is intentionally read-only and is currently used by
`QueueDomainService` for safe status/snapshot and cabinet-info endpoints.
