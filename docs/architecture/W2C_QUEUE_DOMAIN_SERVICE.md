# Wave 2C Queue Domain Service Proposal

Date: 2026-03-07
Mode: analysis-first, updated with Phase 2 compatibility boundary

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
- `get_queue_limits_status(day=..., specialty=...)`
- `get_queue_groups_payload()`
- `get_service_code_mappings_payload()`

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

## Phase 2 Compatibility Boundary Status

Implemented in Wave 2C Phase 2:

- `allocate_ticket(allocation_mode="create_entry", **kwargs)`
- `allocate_ticket(allocation_mode="join_with_token", **kwargs)`

Current behavior:

- the method is a facade only
- it delegates to the existing `queue_service`
- it does not change numbering logic
- it does not change duplicate-policy enforcement
- it does not change `queue_time` semantics

Current limitation:

- only a narrow set of production callers is repointed to this boundary
- direct SQL allocators and legacy `OnlineDay` flows remain outside it
- migration risk is still controlled by characterization tests because the internal allocator has not changed

Current production callers through `allocate_ticket()`:

- `backend/app/api/v1/endpoints/online_queue_new.py::join_queue()`
- `backend/app/services/qr_queue_service.py::complete_join_session()`
- `backend/app/services/qr_queue_service.py::complete_join_session_multiple()`
- `backend/app/services/visit_confirmation_service.py` through
  `QueueContextFacade(QueueDomainServiceContractAdapter)` when a new queue row
  is needed during mounted confirmation
- `backend/app/api/v1/endpoints/registrar_integration.py::create_queue_entries_batch()`
  for mounted batch-only create flow when duplicate gate does not reuse an
  existing specialist-day claim
- `backend/app/services/registrar_wizard_queue_assignment_service.py`
  for mounted wizard-family same-day create flow after queue-tag-level reuse
  and ambiguity checks

## Phase 2.2 Boundary Limits

The current `QueueDomainService.allocate_ticket()` compatibility boundary is not
yet a safe public migration target for all allocator families.

Still outside the safe boundary:

- registrar wizard split allocation
- `qr_queue.py` direct SQL allocator branches
- force-majeure transfer allocator
- all `OnlineDay` legacy allocators
- broader registrar batch service/runtime ownership beyond the mounted create
  branch
- unmounted duplicate confirmation modules

Reason:

- some families still own transaction semantics
- some families still own duplicate-policy shortcuts
- some families are not yet narrowed enough to preserve behavior through a thin
  boundary migration

### Confirmation family note

Mounted confirmation is no longer blocked here:

- Phase 2.4 corrected same-queue duplicate drift
- the current slice moved mounted confirmation queue-row creation through the
  compatibility boundary
- remaining confirmation work is limited to cleanup/dead-path clarification, not
  allocator ownership

### Registrar batch-only note

Mounted registrar batch-only family is now partially migrated:

- reuse and ambiguity logic still live in the mounted router path
- create branch now routes through `QueueDomainService.allocate_ticket()`
- broader registrar wizard/batch service migration is still deferred

### Registrar wizard note

Mounted wizard-family same-day create branch is now migrated:

- queue-tag-level duplicate/reuse logic remains outside the boundary
- the create branch now routes through `QueueDomainService.allocate_ticket()`
- broader wizard/cart orchestration is still outside the queue domain boundary

Notes for the narrowed `W2C-MS-004` slice:

- only queue metadata reads moved under `QueueDomainService`
- static taxonomy definitions still live in `app/services/service_mapping.py`
- no queue numbering, duplicate, lifecycle, or QR-window behavior changed
