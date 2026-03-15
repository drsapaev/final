# Wave 2C QR Direct SQL Readiness

Date: 2026-03-09
Mode: post-migration update
Decision: `mounted full-update family migrated`

## What Is Now True

- public QR join session flows are already boundary-backed through
  `QueueDomainService.allocate_ticket(allocation_mode="join_with_token")`
- the remaining mounted production-relevant QR direct-SQL allocator surface is
  still concentrated in `qr_queue.py::full_update_online_entry()`
- QR additional-service create logic has an explicit QR-local seam
- the QR create-entry payload is now compatible with the current
  `create_entry` boundary path

## What Just Happened

The mounted QR full-update additional-service create branch now goes through:

- `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`

while keeping:

- QR-local raw SQL numbering
- QR-local `queue_time`
- QR-local source inheritance
- QR-local additional-service fan-out

## What Still Has Not Happened

- raw SQL `MAX(number)+1` has not been replaced
- queue-session semantics have not been changed
- broader QR cleanup has not been attempted yet

These are acceptable because the current slice completed caller migration, not
allocator redesign.

## Current Verdict

The production-relevant mounted QR direct-SQL caller migration is complete.

Any further QR work is follow-up work, not a prerequisite for boundary
adoption.
