# Wave 2C Queue Legacy Interaction

Date: 2026-03-07
Mode: analysis-first, docs-only

## Executive Summary

Legacy queue models still matter for numbering review even if they are not the
preferred SSOT path.

The main legacy surfaces are:

- `backend/app/models/online.py` (`OnlineDay`)
- `backend/app/services/online_queue.py`
- `backend/app/api/v1/endpoints/appointments.py`
- `backend/app/crud/queue.py`

These flows keep a second queue-counter model alive in the repo.

## Legacy Interaction Matrix

| File | Legacy mechanism | Does it assign numbers? | Does it touch SSOT `OnlineQueueEntry.number` directly? | Risk to numbering review |
|---|---|---|---|---|
| `backend/app/services/online_queue.py` | `issue_next_ticket()` using `last_ticket` and `start_number` | Yes | No | High conceptual drift |
| `backend/app/api/v1/endpoints/online_queue.py` | Public/legacy endpoint over `issue_next_ticket()` | Yes | No | High conceptual drift |
| `backend/app/api/v1/endpoints/appointments.py` | `open_day`, `close_day`, `stats` over `OnlineDay` and settings | Indirectly controls legacy start-number and open/close semantics | No | Medium to high migration coupling |
| `backend/app/crud/queue.py` | `next_ticket_and_insert_entry()` with `last_ticket` and `ticket_number` | Yes | No, but appears to target older schema naming | High ambiguity / stale path |
| `backend/app/services/board_api_service.py` and related board reads | Read legacy stats | Reads only | No | Low direct risk, but keeps legacy counters user-visible |

## What the Legacy Layer Still Influences

### Start-number semantics

`appointments.py` can still write:

- `queue::{dep}::{date}::open`
- `queue::{dep}::{date}::start_number`

That means the repo still contains operator workflows where queue numbering is
thought of as a department/day counter rather than a `DailyQueue` aggregate rule.

### Open / close semantics

Legacy open/close uses `OnlineDay.is_open`, while SSOT queue flows use
`DailyQueue.opened_at`, `online_start_time`, and `online_end_time`.

This does not directly assign SSOT queue numbers, but it complicates any
attempt to say "there is only one queue policy left".

### Reporting / operator expectations

Legacy stats expose:

- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

These concepts are close enough to SSOT queue behavior that operators may
expect them to remain meaningful, even though they are not driven by the same
runtime objects.

## Can Legacy Create Numbering Drift?

### Direct drift

Not usually in the current SSOT paths.

The inspected legacy services do not directly overwrite
`OnlineQueueEntry.number` in the SSOT queue model.

### Conceptual drift

Yes, clearly.

The repo still contains:

- one model where numbering is `OnlineQueueEntry.number`
- another model where numbering is `last_ticket`
- an additional stale CRUD path using `ticket_number`

That makes migration and policy extraction harder because a reviewer cannot
assume one numbering vocabulary across the codebase.

## Legacy Verdict

Legacy is not the sole blocker for `W2C-MS-005`, but it is a real blocker for
claiming that numbering policy is already centralized.

Best classification:

- legacy does not by itself forbid future extraction
- legacy does prevent calling the current situation "already unified"
- any execution slice touching start-number policy must account for both SSOT
  and legacy operator expectations
