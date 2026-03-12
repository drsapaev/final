# Wave 2C QR Create-Branch Extraction

Date: 2026-03-09
Mode: narrow decomposition, behaviour-preserving
Scope: `qr_queue.py::full_update_online_entry()`

## Old Hidden Create Handoff

Before this slice, the mounted `full_update_online_entry()` endpoint directly
owned the QR additional-service create branch inline:

- resolve target queue by `service.queue_tag`
- auto-create `DailyQueue` if missing
- assign number with raw SQL `MAX(number)+1`
- allocate `session_id` with `get_or_create_session_id(...)`
- create independent `OnlineQueueEntry`

That logic existed inside both:

- first-fill QR additional-service branch
- edit-existing additional-service branch

## New Explicit QR-Local Seam

The QR family now has an explicit local seam in:

- [qr_full_update_queue_assignment_service.py](C:/final/backend/app/services/qr_full_update_queue_assignment_service.py)

Key artifacts:

- `QRFullUpdateCreateBranchHandoff`
- `QRFullUpdateQueueAssignmentService.prepare_create_branch_handoffs(...)`
- `QRFullUpdateQueueAssignmentService.materialize_create_branch_handoffs(...)`

## New Runtime Shape

Mounted endpoint still owns overall orchestration, but the create branch is now:

1. `full_update_online_entry()` determines `new_service_ids`
2. endpoint delegates QR additional-service create prep to
   `QRFullUpdateQueueAssignmentService.prepare_create_branch_handoffs(...)`
3. endpoint delegates create materialization to
   `QRFullUpdateQueueAssignmentService.materialize_create_branch_handoffs(...)`
4. raw SQL numbering still happens inside the QR-local seam, not inline in the endpoint

## What Stayed Unchanged

- consultation still keeps original QR `queue_time`
- additional services still create independent entries
- raw SQL `MAX(number)+1` still remains
- new additional-service rows still get current local time
- `source` still inherits `entry.source or "online"`
- response shape is unchanged
- public QR join flows are untouched

## What Still Remains Direct-SQL

This slice extracted the handoff but did not replace the allocator.

Direct SQL still remains in QR family inside the new QR-local seam:

- `_allocate_next_number()` still runs `MAX(number)+1`
- `_materialize_create_branch_handoff()` still creates `OnlineQueueEntry` directly

That is intentional for this phase. The goal was explicit seam isolation, not
allocator replacement.
