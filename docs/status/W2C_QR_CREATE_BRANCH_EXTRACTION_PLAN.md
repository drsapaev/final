# Wave 2C QR Create-Branch Extraction Plan

Date: 2026-03-09
Mode: narrow decomposition, behaviour-preserving
Target: `backend/app/api/v1/endpoints/qr_queue.py::full_update_online_entry()`

## Current Hidden Create Handoff

`full_update_online_entry()` currently performs QR-specific additional-service
allocation inline inside the mounted endpoint.

Two mounted runtime branches do this:

1. first-fill QR branch (`is_first_fill_qr`)
2. edit-existing branch (`new_service_ids` during editing)

Both branches currently:

- resolve target queue by `service.queue_tag`
- auto-create `DailyQueue` if missing
- assign number via raw SQL `MAX(number)+1`
- allocate `session_id` via `get_or_create_session_id(...)`
- create independent `OnlineQueueEntry` rows inline

## What Will Be Extracted

A QR-local create-branch seam that owns:

- target queue resolution for additional services
- current-local-time capture for independent additional-service rows
- handoff preparation for each additional service
- raw-SQL materialization of independent entries

## What Must Remain Unchanged

- consultation keeps original QR `queue_time`
- additional services still create independent entries
- raw SQL numbering remains as-is for now
- new additional-service rows keep current local time
- `source` stays `entry.source or "online"`
- same-day / future-day behavior remains unchanged
- mounted response shape remains unchanged
- `queue_session.py` semantics remain untouched

## Why This Is Safe

- extraction changes ownership of the create-branch handoff, not the numbering
  algorithm itself
- public QR join flows remain out of scope
- visit/billing sync orchestration remains in the mounted endpoint
- characterization tests already pin the runtime behavior that must stay intact

## New Seam Target

The endpoint should keep orchestration, but the QR-specific additional-service
create branch should become an explicit QR-local seam that can later be swapped
to `QueueDomainService.allocate_ticket()` during a dedicated migration slice.
