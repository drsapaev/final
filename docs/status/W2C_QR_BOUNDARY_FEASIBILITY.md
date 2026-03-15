# Wave 2C QR Boundary Feasibility

Date: 2026-03-09
Mode: docs-only readiness review

## Question

Can the extracted QR-local create seam now be replaced with
`QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`
without changing:

- numbering behavior
- `queue_time` behavior
- source inheritance
- fairness ordering
- additional-service semantics
- clinic-wide QR fan-out semantics

## Short Answer

Not yet.

## What Already Fits The Boundary

- The create branch is now explicit and isolated.
- `QueueDomainService.allocate_ticket()` already supports
  `allocation_mode="create_entry"`.
- The QR seam already resolves the target queue before row creation.
- The QR seam can continue to own:
  - consultation-vs-additional-service split
  - queue-tag routing
  - current-time assignment for new additional-service rows

These points mean the family no longer needs another structural extraction.

## What Still Prevents A Safe Swap

### 1. QR create payload is wider than current boundary create contract

Current QR materialization preserves extra patient fields on the new row:

- `birth_year`
- `address`

The current `queue_service.create_queue_entry(...)` compatibility path does not
accept or write those fields.

Result:

- a direct swap to `QueueDomainService.allocate_ticket(... create_entry ...)`
  would risk dropping persisted patient metadata for QR-created additional
  service rows
- that is observable runtime drift, not just an internal cleanup detail

### 2. QR seam currently writes JSON-shaped service payloads directly

The QR seam materializes:

- `services_json`
- `service_codes_json`

Current compatibility boundary can forward create-entry arguments, but it does
not define a QR-specific adapter contract for this payload shape.

This is a narrower issue than the original monolith, but it still means the QR
create handoff is not yet a drop-in boundary caller.

## What Does Not Block Migration By Itself

### Raw SQL numbering assumption

Not the immediate blocker for the next step.

- It remains a future migration concern.
- The readiness question here is caller compatibility, not allocator redesign.

### Missing canonical duplicate gate

Not the immediate blocker for this caller migration.

- `allocate_ticket(create_entry)` is currently a compatibility facade, not the
  final duplicate-policy owner.
- A behavior-preserving migration may keep the current QR duplicate gap and fix
  it later as a separate slice.

### `queue_session` active-set mismatch

Not the immediate blocker for this caller migration.

- Both the current QR seam and the current legacy boundary path rely on the
  same `get_or_create_session_id(...)` helper.

## Feasibility Verdict

The family is close, but not ready for direct boundary migration.

Verdict:

- one more narrow fix is required
- that fix should widen the supported create-entry handoff so the boundary can
  preserve QR row fields 1:1
