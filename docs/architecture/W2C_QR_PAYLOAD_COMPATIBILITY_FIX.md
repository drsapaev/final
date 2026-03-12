# Wave 2C QR Payload Compatibility Fix

Date: 2026-03-09
Mode: behaviour-preserving compatibility fix

## Old Compatibility Gap

The mounted QR full-update family was already structurally ready for a boundary
swap, but one compatibility gap remained:

- the QR-local create seam preserved `birth_year`
- the QR-local create seam preserved `address`
- the future boundary target
  `QueueDomainService.allocate_ticket(allocation_mode="create_entry")`
  delegated to `queue_service.create_queue_entry(...)`
- that create-entry path did not yet persist those fields

This meant a direct caller migration would risk data loss on newly created
QR additional-service rows.

## New Compatible Path

The gap is now closed in two narrow steps:

1. `QRFullUpdateQueueAssignmentService` can build boundary-compatible
   create-entry kwargs via `build_create_entry_kwargs(...)`
2. `queue_service.create_queue_entry(...)` now persists:
   - `birth_year`
   - `address`

The QR-local handoff payload is now aligned with the create-entry boundary:

- `services`
- `service_codes`
- `birth_year`
- `address`
- `source`
- `status`
- `queue_time`
- `total_amount`

## Why Behavior Is Preserved

- mounted QR runtime still uses the same QR-local direct materialization path
- raw SQL `MAX(number)+1` remains unchanged
- consultation still keeps original `queue_time`
- additional-service rows still get current local time
- source inheritance remains `entry.source or "online"`
- response shape did not change

## What This Enables

The family is now compatible with a later boundary migration because the
create-entry boundary can preserve the current QR payload 1:1.

This slice does not perform that migration. It only removes the payload-shape
blocker so the next execution unit can be the actual QR boundary migration.
