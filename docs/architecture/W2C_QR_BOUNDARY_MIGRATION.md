# Wave 2C QR Boundary Migration

Date: 2026-03-09
Mode: narrow caller migration

## Scope

This slice migrates only the mounted QR full-update additional-service create
branch.

In scope:

- `backend/app/services/qr_full_update_queue_assignment_service.py`
- the mounted `full_update_online_entry()` flow that already delegates to that
  QR-local seam

Out of scope:

- public `/queue/join/start`
- public `/queue/join/complete`
- `queue_session` semantics
- raw SQL numbering redesign
- force-majeure
- `OnlineDay`

## Old Path

Before this slice, the mounted QR full-update family used:

1. `full_update_online_entry()`
2. `QRFullUpdateQueueAssignmentService.prepare_create_branch_handoffs(...)`
3. `QRFullUpdateQueueAssignmentService._materialize_create_branch_handoff(...)`
4. QR-local raw SQL `MAX(number)+1`
5. direct `OnlineQueueEntry(...)` creation + `db.add(...)`

That meant the create branch was already isolated, but it still bypassed the
public queue allocation boundary.

## New Path

After this slice, the mounted QR full-update family uses:

1. `full_update_online_entry()`
2. `QRFullUpdateQueueAssignmentService.prepare_create_branch_handoffs(...)`
3. `QRFullUpdateQueueAssignmentService.build_create_entry_kwargs(...)`
4. QR-local raw SQL `MAX(number)+1`
5. `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`
6. legacy `queue_service.create_queue_entry(...)`

The QR-local seam still owns:

- target queue resolution
- current local `queue_time` for new additional-service rows
- raw SQL numbering
- QR-specific payload preparation

The compatibility boundary now owns row creation.

## Why Behavior Is Preserved

- consultation rows still keep the original `queue_time`
- new additional-service rows still create independent queue entries
- numbering still comes from the same QR-local raw SQL allocator
- `queue_time` for new additional-service rows is still computed in the QR seam
- `source` still inherits `entry.source or "online"`
- QR payload fields such as `birth_year` and `address` still persist
- response shape is unchanged because endpoint orchestration is unchanged

## What Remains Outside The Boundary

- raw SQL numbering assumptions inside the QR-local seam
- QR-specific duplicate-policy gaps before additional-service create
- `queue_session` active-status mismatch
- non-mounted / broader QR cleanup

This is expected. The slice migrates the caller only; it does not redesign the
allocator internals.
