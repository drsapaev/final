# Wave 2C Queue Domain Service Proposal

Date: 2026-03-06
Mode: analysis-first

## Goal

Introduce a `QueueDomainService` that owns queue lifecycle rules without directly using ORM queries from routers.

Target shape:

- router validates input and permissions
- router calls `QueueDomainService`
- `QueueDomainService` orchestrates queue lifecycle
- repositories perform persistence
- side effects run through explicit adapters after commit

## Why a Dedicated Domain Service Is Needed

Current queue behavior is fragmented across:

- QR queue runtime handlers
- registrar queue flows
- doctor queue flows
- visit lifecycle handlers
- legacy appointments queue administration

A single domain service is needed to own:

- transition validation
- active-status policy
- numbering and duplicate policy
- visit/queue synchronization rules
- side-effect dispatch order

## Proposed Responsibilities

`QueueDomainService` should own:

- enqueueing a visit or direct queue request
- queue-number allocation orchestration
- queue-position and active-state policy
- calling the next patient
- marking patient in service
- sending patient to diagnostics
- completing or closing a queue entry
- canceling or rescheduling queue-linked entries
- restoring inactive patients back into the queue
- reorder orchestration

`QueueDomainService` should not own:

- raw HTTP request/response handling
- direct ORM querying in routers
- payment reconciliation logic
- frontend-specific shaping
- websocket transport details

## Proposed Method Signatures

These signatures are intentionally narrow. They are designed for gradual migration, not a full rewrite.

```python
class QueueDomainService:
    def enqueue_visit(
        self,
        *,
        day: date,
        specialist_id: int,
        queue_tag: str | None,
        patient_id: int | None,
        patient_name: str | None,
        phone: str | None,
        telegram_id: int | None,
        visit_id: int | None,
        services: list[dict[str, Any]] | None,
        source: str,
        created_by_user_id: int | None,
        queue_time: datetime | None = None,
        allow_duplicate: bool = False,
    ) -> QueueEntryResult:
        ...

    def call_next(
        self,
        *,
        specialist_id: int,
        day: date,
        called_by_user_id: int,
    ) -> QueueCallResult:
        ...

    def mark_in_service(
        self,
        *,
        entry_id: int,
        actor_user_id: int,
        visit_id: int | None = None,
    ) -> QueueEntryResult:
        ...

    def send_to_diagnostics(
        self,
        *,
        entry_id: int,
        actor_user_id: int,
    ) -> QueueEntryResult:
        ...

    def complete_visit(
        self,
        *,
        entry_id: int,
        actor_user_id: int,
        visit_id: int | None = None,
        result_status: str = "served",
    ) -> QueueEntryResult:
        ...

    def cancel_visit_queue_link(
        self,
        *,
        visit_id: int,
        actor_user_id: int,
        reason: str | None = None,
    ) -> QueueEntryResult | None:
        ...

    def reschedule_visit_queue_link(
        self,
        *,
        visit_id: int,
        actor_user_id: int,
        new_day: date,
    ) -> QueueEntryResult | None:
        ...

    def restore_as_next(
        self,
        *,
        entry_id: int,
        actor_user_id: int,
    ) -> QueueEntryResult:
        ...

    def reorder_active_entries(
        self,
        *,
        queue_id: int,
        entry_orders: list[dict[str, int]],
        actor_user_id: int,
    ) -> QueueReorderResult:
        ...

    def get_queue_snapshot(
        self,
        *,
        queue_id: int,
    ) -> QueueSnapshot:
        ...
```

## Internal Rules the Service Must Own

### Canonical status handling

The service should normalize current aliases internally:

- `in_progress` -> `in_service`
- `canceled` -> `cancelled`
- `completed` -> `served` for queue rows

### Transaction boundaries

The service should own the commit boundary for:

- queue entry creation
- queue status changes
- visit-linked queue updates
- reorder changes

If visit + queue must change together, the service should orchestrate both repositories inside one unit of work.

### Post-commit side effects

Side effects should be emitted after persistence succeeds:

- display websocket update
- queue websocket update
- queue position notifications
- registrar or doctor dashboard refresh hooks

This can be a simple adapter layer first. It does not need a full event bus in the first migration slice.

## Interaction with Visits Service

Recommended boundary:

- `VisitsApiService` owns visit HTTP use cases
- `QueueDomainService` owns queue consequences of visit changes

Examples:

- cancel visit:
  - visit service validates visit rule
  - queue domain service updates linked queue state
- reschedule visit:
  - visit service changes visit date
  - queue domain service marks or migrates queue link according to policy

Direct raw SQL from `visits.py` to `queue_entries` should be considered a migration target, not an acceptable end state.

## Interaction with Registrar Flow

Registrar flows need queue orchestration for:

- batch queue entry creation
- queue-linked visit start
- large queue read models

Recommended boundary:

- registrar routers call thin application services
- those services call `QueueDomainService` for lifecycle mutation

This keeps registrar orchestration out of routers without moving payment logic into the queue domain.

## Interaction with Payment Track

Wave 2C should not absorb payment reconciliation.

For payment-coupled completion paths:

- queue domain service can return a domain result or event
- payment track handles invoice/provider/billing consequences separately

That avoids turning queue refactor into Wave 2D by accident.

## Recommended First Adoption Order

1. Introduce the service with no router migrations yet.
2. Move read-only queue snapshot and number-allocation helpers behind it.
3. Move one mutation family at a time:
   - call next
   - no show / restore
   - diagnostics / incomplete
   - visit-linked cancel/reschedule
4. Leave payment-coupled completion paths for later queue/payment coordination work.

## Phase 1 Implementation Status

Implemented in `backend/app/services/queue_domain_service.py`.

Currently implemented:

- `get_queue_snapshot(queue_id=...)`
- `get_queue_snapshot_by_specialist_day(specialist_id=..., day=...)`
- `list_queue_cabinet_info(day=..., specialist_id=..., cabinet_number=...)`
- `get_queue_cabinet_info(queue_id=...)`

Skeleton-only methods that intentionally still raise `NotImplementedError`:

- `enqueue`
- `call_next`
- `mark_in_service`
- `complete_visit`
- `cancel_queue_link`
- `reschedule_queue_link`

This is intentional for Phase 1:

- read-only queue slices can adopt the service now
- mutation flows stay in legacy paths until the state machine and transaction rules
  are migrated explicitly
