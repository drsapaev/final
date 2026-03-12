# Wave 2C QR Direct SQL Inventory

Date: 2026-03-09
Mode: characterization-first, migration-prep
Scope: QR queue family with emphasis on direct SQL allocator usage

## Summary

Production QR join flows are no longer the direct-SQL problem area:

- `POST /api/v1/queue/join/start` is session bootstrap only
- `POST /api/v1/queue/join/complete` is boundary-backed through `QueueDomainService.allocate_ticket(allocation_mode="join_with_token")`
- remaining mounted direct-SQL allocator behavior is concentrated in
  `PUT /api/v1/queue/online-entry/{entry_id}/full-update`

## Inventory

| File | Function / Path | Mounted | Production Relevant | Direct SQL | Numbering Logic | Duplicate Logic | Session / Token Dependency | Source Semantics | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `backend/app/api/v1/endpoints/qr_queue.py` | `start_join_session()` / `POST /api/v1/queue/join/start` | yes | yes | no | none; creates pending join session only | none at this step | yes, creates `QueueJoinSession` from QR token | no queue entry created yet | low |
| `backend/app/api/v1/endpoints/qr_queue.py` | `complete_join_session()` / `POST /api/v1/queue/join/complete` | yes | yes | no | delegates to `QRQueueService.complete_join_session*()` | delegated to boundary-backed QR join logic | yes, consumes `session_token` | `source="online"` on join | low |
| `backend/app/services/qr_queue_service.py` | `complete_join_session()` | yes, via mounted router | yes | no | `QueueDomainService.allocate_ticket(allocation_mode="join_with_token")` | legacy duplicate gate via `queue_service.check_uniqueness(...)` inside boundary | yes, pending session + QR token | `source="online"` | low |
| `backend/app/services/qr_queue_service.py` | `complete_join_session_multiple()` | yes, via mounted router | yes | no | same boundary path with `specialist_id_override` | same duplicate behavior per selected specialist/profile | yes, pending session + QR token | `source="online"` | low |
| `backend/app/api/v1/endpoints/qr_queue.py` | `full_update_online_entry()` first-fill additional-service branch | yes | yes | yes | raw `SELECT COALESCE(MAX(number), 0) + 1 FROM queue_entries WHERE queue_id = :qid` | no canonical duplicate gate before creating independent additional-service entry | indirect; allocates `session_id` via `get_or_create_session_id(...)` | reuses `entry.source or "online"` | high |
| `backend/app/api/v1/endpoints/qr_queue.py` | `full_update_online_entry()` edit-existing additional-service branch | yes | yes | yes | same raw SQL `MAX(number)+1` pattern per target queue | no canonical duplicate gate before creating additional independent entry | indirect; allocates `session_id` via `get_or_create_session_id(...)` | reuses `entry.source or "online"` | high |
| `backend/app/api/v1/endpoints/qr_queue.py` | disabled `if False` new-service fan-out branch | no | no | no direct SQL; uses `queue_service.get_next_queue_number(...)` | manual legacy numbering helper | no runtime impact because branch is disabled | would use `session_id` | `entry.source or "desk"` in code path | none / non-runtime |

## What Is Actually Left

The remaining production-relevant QR allocator problem is not the public
session-based QR join flow. It is the monolithic `full_update_online_entry()`
path, specifically the branches that create independent queue entries for
additional services using raw SQL numbering.

## Evidence Notes

- Direct raw SQL numbering appears in two mounted branches:
  - first-fill QR branch around `qr_queue.py:1686`
  - edit-existing branch around `qr_queue.py:1863`
- Clinic-wide and single-specialist QR join flows are already routed through
  `QueueDomainService.allocate_ticket(allocation_mode="join_with_token")`
  in `qr_queue_service.py`.
