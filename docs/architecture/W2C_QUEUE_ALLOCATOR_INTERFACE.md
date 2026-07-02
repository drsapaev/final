# Wave 2C Queue Allocator Interface

Date: 2026-03-07
Mode: analysis-first, docs-only

## Purpose

This document defines the proposed public interface for the future queue
allocator.

It is intentionally a contract only. No runtime implementation is introduced in
this phase.

## Public Owner

`QueueDomainService`

## Proposed Public Method

```python
allocate_ticket(
    *,
    queue_id: int,
    queue_day: date | None = None,
    patient_id: int | None = None,
    phone: str | None = None,
    telegram_id: int | None = None,
    source: str,
    queue_time: datetime | None = None,
    allow_duplicate: bool = False,
    duplicate_override_reason: str | None = None,
    idempotency_key: str | None = None,
) -> TicketAllocationResult
```

## Inputs

| Input | Meaning | Notes |
|---|---|---|
| `queue_id` | concrete `DailyQueue` target | required |
| `queue_day` | optional safety check against `DailyQueue.day` | helps defend against stale caller assumptions |
| `patient_id` | preferred canonical identity | may be absent in public join flows |
| `phone` | fallback identity input | normalized before duplicate evaluation |
| `telegram_id` | fallback identity input | normalized before duplicate evaluation |
| `source` | creation source such as `online`, `desk`, `morning_assignment`, `confirmation` | required for audit and source-specific policy branches |
| `queue_time` | fairness timestamp to persist with the entry | if absent, service determines default timestamp |
| `allow_duplicate` | explicit override switch | default must be `False` |
| `duplicate_override_reason` | audit explanation when override is used | required if override is true |
| `idempotency_key` | optional caller-level replay key | useful for QR/session-based retries |

## Output Shape

```python
class TicketAllocationResult(TypedDict):
    decision: Literal["allocated", "duplicate", "blocked"]
    queue_id: int
    queue_day: date
    ticket_number: int | None
    queue_time: datetime | None
    canonical_identity: str | None
    existing_entry_id: int | None
    duplicate_reason: str | None
    source: str
```

## Expected Semantics

### `decision = "allocated"`

- a new ticket number is assigned
- the result carries the new `ticket_number`
- later queue-entry persistence must occur in the same transaction boundary

### `decision = "duplicate"`

- an active queue row already exists for the canonical identity in the same
  queue/day
- the result references `existing_entry_id`
- no new ticket number is allocated

### `decision = "blocked"`

- allocation is not allowed because queue policy, state, or input validation
  failed
- no ticket number is allocated

## Failure Cases

The interface must be able to signal at least these failures:

- queue not found
- queue/day mismatch
- queue closed for the current source
- missing usable identity
- duplicate exists and no override is allowed
- allocator contention / concurrency failure
- unsupported legacy path that must stay outside the new contract

## Idempotency Expectations

The allocator should be idempotent for replayed requests that represent the same
queue join intent.

### Minimum expectation

If the same caller replays the same join intent for the same queue/day and the
same canonical identity already has an active row, the result should be
`duplicate`, not a second ticket allocation.

### Stronger optional expectation

If a future caller provides a stable `idempotency_key`, the domain service may
tie retries directly to the first allocation decision.

## Boundary Rules

### Allowed

- repositories provide internal persistence primitives
- domain service normalizes identity and source
- domain service evaluates duplicate policy before allocation

### Not allowed

- routers calling repository-level allocation directly
- public split workflow that reserves a ticket without domain ownership
- direct SQL `MAX(number)+1` in feature routers

## Internal Repository Needs

The public interface implies private lower-level operations such as:

- `resolve_queue(queue_id)`
- `find_existing_active_entry(identity, queue_id, day)`
- `reserve_next_ticket_number(queue_id, day)`
- `insert_queue_entry(...)`

Those are not public API. They are implementation details behind the domain
owner.
