# Wave 2C Queue Numbering Flows

Date: 2026-03-07
Mode: analysis-first, docs-only

## Executive Summary

Runtime queue-number assignment depends on entry source and feature path.

The main flows are:

- online booking / QR token join
- registrar desk batch queue creation
- QR "full update" add-service flow
- morning assignment
- confirmation-based queue creation
- telegram-assisted online join
- legacy department/day ticket issue

These flows are not fully unified around one allocator or one duplicate policy.

## Runtime Flow Table

| Flow | Entry point | Where number is assigned | Where entry is created | `queue_time` behavior | Fallback / special logic |
|---|---|---|---|---|---|
| Online booking | `backend/app/api/v1/endpoints/queue.py`, `backend/app/api/v1/endpoints/online_queue_new.py` | `queue_service.get_next_queue_number()` via `create_queue_entry(auto_number=True)` inside `join_queue_with_token()` | `queue_service.create_queue_entry()` | `queue_time` is set at creation time and returned to caller | QR token decides queue/day; clinic-wide token may resolve specialist dynamically |
| Telegram queue join | same join path, but with `telegram_id` | Same as online booking | Same as online booking | Same as online booking | No separate telegram allocator; telegram only changes identity/duplicate check input |
| QR queue service join session | `backend/app/services/qr_queue_service.py` | Delegates to `queue_service.join_queue_with_token()` | Delegates to `queue_service.create_queue_entry()` | Preserves join-time business timestamp | Session and token metadata are stored separately from entry number |
| Registrar desk batch | `backend/app/api/v1/endpoints/registrar_integration.py:create_queue_entries_batch()` | `queue_service.create_queue_entry(... auto_number=True)` | `queue_service.create_queue_entry()` | Explicitly passes `current_time` for fairness | Duplicate policy is checked separately by patient/queue before creation |
| Registrar older desk path | legacy branch in `registrar_integration.py` | `start_number + current_count` | Direct `QueueEntry(...)` create | No explicit fairness timestamp in the inspected branch | Uses older queue model path, not SSOT queue helper |
| QR full update / add new service | `backend/app/api/v1/endpoints/qr_queue.py:full_update_online_entry()` | In two branches: direct SQL `MAX(number)+1`, and one branch via `queue_service.get_next_queue_number()` | Direct `OnlineQueueEntry(...)` creation | Existing services keep original `queue_time`; newly added services get current edit time | This is the clearest runtime split between fairness-time intent and mixed numbering implementations |
| Morning assignment | `backend/app/services/morning_assignment.py` | `queue_service.create_queue_entry(... auto_number=True)` | `queue_service.create_queue_entry()` | Uses assignment-run timestamp as business time | Reuses or creates `session_id`; source is usually `morning_assignment` |
| Visit confirmation | `backend/app/services/visit_confirmation_service.py` | Calls `queue_service.get_next_queue_number()` first | Calls `queue_service.create_queue_entry(number=next_number, ...)` | Uses service defaults unless passed in later | Split numbering and creation into separate steps |
| Registrar wizard confirmation path | `backend/app/services/registrar_wizard_api_service.py` | Calls `queue_service.get_next_queue_number()` | Direct `OnlineQueueEntry(number=next_number, ...)` | Sets current local time as business timestamp | Partial bypass of central creation helper |
| Force majeure transfer | `backend/app/services/force_majeure_service.py` | `_get_next_queue_number()` | Transfer flow creates new tomorrow entry | New queue/day means a new ordering baseline | Uses separate allocator that ignores cancelled entries |
| Legacy online queue | `backend/app/services/online_queue.py:issue_next_ticket()` | `last_ticket -> next_ticket` in settings store | Legacy counter update only; separate legacy queue record flow | No `queue_time`; uses legacy counters | Runs on `OnlineDay` + settings, not `OnlineQueueEntry` |

## Flow Notes

### Online booking / QR join

- `QueueToken` is validated first.
- The number is assigned only when queue entry creation happens.
- `telegram_id` and `phone` affect duplicate detection, not numbering rules.

### Registrar desk batch

- This is the cleanest registrar-side SSOT path.
- It still depends on a separate duplicate check before calling
  `create_queue_entry()`.

### QR full update / add-service

- This is the highest-risk modern flow for numbering policy.
- The feature intentionally preserves original `queue_time` for unchanged
  services and gives newly added services the current edit time.
- Number allocation in the same feature is not centralized.

### Confirmation-based flows

- Both confirmation paths rely on the service allocator for the number itself.
- They do not consistently use `create_queue_entry(auto_number=True)`.
- This keeps the "ask for number, then create row" split alive.

### Legacy flows

- `OnlineDay` and `Setting(category="queue")` still run their own counters.
- That counter does not directly write `OnlineQueueEntry.number`, but it keeps a
  second numbering model alive in the repo.

## Flow-Level Verdict

The runtime flow map does not support a safe "extract just the numbering
boundary" change yet.

Before `W2C-MS-005` can execute safely, the codebase needs a domain decision on:

- the one true allocator API
- whether callers may request a number separately from entry creation
- how confirmation, QR full-update, and force-majeure flows are expected to
  integrate with that allocator
