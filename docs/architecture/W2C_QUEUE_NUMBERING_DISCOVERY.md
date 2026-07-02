# Wave 2C Queue Numbering Discovery

Date: 2026-03-07
Mode: analysis-first, docs-only
Scope: queue numbering sources only

## Executive Summary

Queue numbering is not owned by a single runtime boundary.

The current repo contains five distinct numbering mechanisms:

1. SSOT-style allocation through `QueueBusinessService.get_next_queue_number()` and
   `create_queue_entry()`
2. Direct `SELECT COALESCE(MAX(number), 0) + 1` allocation in `qr_queue.py`
3. Legacy registrar allocation with `start_number + current_count`
4. Separate legacy ticket counters through `OnlineDay` and
   `Setting(category="queue")`
5. Specialized transfer/recovery allocators such as `ForceMajeureService`

`QueueToken` is not the numbering source. It gates or routes queue joins, while
the actual queue number is assigned later by one of the mechanisms below.

## Numbering Source Matrix

| File | Function / path | How the number is created | Uses `QueueToken` | Race protection | Transaction boundary | Notes |
|---|---|---|---|---|---|---|
| `backend/app/services/queue_service.py` | `calculate_next_number()` | `max(number) + 1` inside one `daily_queue`, then `max(..., start_number)` | No | No explicit row lock; relies on session/transaction discipline | Shared with caller; often `flush` + outer commit | Main SSOT-style allocator |
| `backend/app/services/queue_service.py` | `get_next_queue_number()` | Delegates to `calculate_next_number()` for `scope="per_queue"`; can also do global `max(number) + 1` | No | No explicit lock | Shared with caller | Central helper, but not the only runtime allocator |
| `backend/app/services/queue_service.py` | `create_queue_entry()` | If `number is None` or `auto_number=True`, calls `get_next_queue_number()` | No | Same as above | Shared with caller | Preferred creation path for several modern flows |
| `backend/app/services/queue_service.py` | `join_queue_with_token()` | Calls `create_queue_entry(... auto_number=True, commit=False)` | Yes, as join gate only | Same as service allocator | Single commit after token usage increment | QR/online join path |
| `backend/app/api/v1/endpoints/qr_queue.py` | `full_update_online_entry()` new-service branches | Direct SQL `SELECT COALESCE(MAX(number), 0) + 1 FROM queue_entries WHERE queue_id = :qid` | No | No explicit lock | Inside larger write transaction | Bypasses central service allocator |
| `backend/app/api/v1/endpoints/qr_queue.py` | `full_update_online_entry()` later branch | Calls `queue_service.get_next_queue_number()` | No | Same as service allocator | Inside larger write transaction | Same feature area uses two allocation styles |
| `backend/app/api/v1/endpoints/registrar_integration.py` | legacy desk-create branch near `next_number = start_number + current_count` | `count(queue entries)` + `start_number` | No | None | Same request transaction | Uses older queue model path |
| `backend/app/api/v1/endpoints/registrar_integration.py` | `create_queue_entries_batch()` | Calls `queue_service.create_queue_entry(... auto_number=True)` | No | Same as service allocator | Batch commit at end | Modern registrar batch path |
| `backend/app/services/morning_assignment.py` | `_assign_single_queue()` | Calls `queue_service.create_queue_entry(... auto_number=True)` | No | Same as service allocator | One batch commit in assignment run | Uses current assignment timestamp as `queue_time` |
| `backend/app/services/visit_confirmation_service.py` | confirmation queue creation | Calls `queue_service.get_next_queue_number()` first, then passes explicit `number` into `create_queue_entry()` | No | Same as service allocator | Shared with outer confirmation flow | Split numbering and creation responsibilities |
| `backend/app/services/registrar_wizard_api_service.py` | confirmation/registrar wizard queue creation | Calls `queue_service.get_next_queue_number()` and then creates `OnlineQueueEntry(number=next_number, ...)` directly | No | Same as service allocator | Shared with wizard flow | Partial bypass of `create_queue_entry()` |
| `backend/app/crud/online_queue.py` | legacy/transitional join helpers | Calls `queue_service.get_next_queue_number()`, then constructs `OnlineQueueEntry(number=next_number, ...)` directly | Sometimes | Same as service allocator | Per-request commit | Transitional layer still duplicates behavior |
| `backend/app/services/force_majeure_service.py` | `_get_next_queue_number()` | Reads highest non-cancelled number ordered descending, then `+ 1` | No | No explicit lock | Shared with transfer flow | Separate allocator for tomorrow-transfer flow |
| `backend/app/services/online_queue.py` | `issue_next_ticket()` | Legacy `last_ticket` counter in settings store | No | Counter is updated in one request transaction, but separate from SSOT queue tables | Immediate commit | Legacy department/day queue system |
| `backend/app/crud/queue.py` | `next_ticket_and_insert_entry()` | Updates `daily_queues.last_ticket` and inserts `ticket_number = new_no` | No | None beyond current transaction | Immediate commit | Legacy/stale CRUD path with old column names |

## Observations

- The repo does not have a single "number allocation owner".
- The main modern path is `queue_service.get_next_queue_number()` plus
  `create_queue_entry()`, but it is not enforced.
- `QueueToken` does not allocate numbers. It only authorizes a join flow and
  stores metadata such as day, specialist, and clinic-wide scope.
- Several callers split the lifecycle into two steps:
  1. ask for `next_number`
  2. create `OnlineQueueEntry` separately
- That split increases the chance of drift between numbering policy and entry
  creation policy.

## Immediate Implications for `W2C-MS-005`

`W2C-MS-005` is not a simple repository extraction.

It would need to decide which of the following becomes normative:

- service allocator only
- direct SQL allocator compatibility
- registrar count-based allocator compatibility
- legacy `OnlineDay` counter compatibility
- force-majeure transfer allocator compatibility

That is a domain decision, not a read-only cleanup.
