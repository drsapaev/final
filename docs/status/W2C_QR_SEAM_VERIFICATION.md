# Wave 2C QR Seam Verification

Date: 2026-03-09
Mode: docs-only readiness recheck
Scope: mounted `qr_queue.py::full_update_online_entry()`

## Verdict

QR create-branch seam is isolated enough for a boundary-readiness decision.

## What Was Verified

1. Mounted `full_update_online_entry()` no longer owns the additional-service
   create branch inline.
2. QR family now has an explicit QR-local seam in
   `QRFullUpdateQueueAssignmentService`.
3. The remaining direct-SQL numbering and row materialization behavior is
   localized inside that QR-local seam.
4. No additional hidden allocator loop remains inside the mounted endpoint for
   the characterized QR additional-service branch.

## Runtime Evidence

- `qr_queue.py` now calls:
  - `prepare_create_branch_handoffs(...)`
  - `materialize_create_branch_handoffs(...)`
  in both the first-fill and edit-existing additional-service branches.
- `QRFullUpdateQueueAssignmentService` now owns:
  - target queue resolution
  - create-branch payload shaping
  - raw-SQL next-number allocation
  - direct `OnlineQueueEntry` materialization

## What Remains Shared

- `queue_service.get_or_create_daily_queue(...)` is still used for missing
  target queues.
- `get_or_create_session_id(...)` is still used for session grouping.
- `QueueDomainService.allocate_ticket(...)` still delegates only to
  `queue_service.create_queue_entry(...)` and `join_queue_with_token(...)`.

These shared pieces are no longer hidden inside the mounted endpoint. They are
dependencies of the QR-local seam, which is the correct narrowing for the next
migration decision.

## Conclusion

This family is no longer blocked by structural invisibility of the allocator
surface. Any remaining blocker is now about contract compatibility, not about
finding the migration point.
