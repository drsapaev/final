# Wave 2C Queue State Machine

Date: 2026-03-06
Mode: analysis-first
Source of truth for this document: current backend code, not legacy docs

## Scope

This state machine describes actual queue lifecycle behavior observed in code today.
It is not a target design yet. It is the baseline needed before any refactor.

## State Families

### Canonical queue-entry states found in `OnlineQueueEntry`

- `waiting`
- `called`
- `in_service`
- `diagnostics`
- `served`
- `incomplete`
- `no_show`
- `cancelled`

### Extra states found in runtime handlers

- `canceled`
- `rescheduled`
- `in_progress`
- `completed`

These extra states are evidence of drift:

- `canceled` vs `cancelled`
- `in_progress` vs `in_service`
- `completed` vs `served`

## Transition Table

| From | To | Trigger / actor | Current implementation | Side effects | Notes |
|---|---|---|---|---|---|
| `created` | `waiting` | QR join, registrar batch create, morning assignment, direct queue creation | `queue_service.join_queue_with_token`, `queue_service.create_queue_entry`, `registrar_integration.create_queue_entries_batch`, `morning_assignment.run_morning_assignment` | Number allocation, session reuse, queue time assignment | Entry creation path is spread across multiple callers |
| `waiting` | `called` | Doctor or registrar calls next patient | `qr_queue_service.call_next_patient`; doctor queue call handler also writes `called` | Sets `called_at`; downstream display/push notifications | One of the few consistent transitions |
| `waiting` | `no_show` | Doctor or registrar marks absent | `qr_queue.mark_entry_no_show` | Queue update broadcast/display side effects | Allowed only from `waiting` or `called` |
| `called` | `no_show` | Doctor or registrar marks absent | `qr_queue.mark_entry_no_show` | Queue update broadcast/display side effects | Allowed only from `waiting` or `called` |
| `no_show` | `waiting` | Doctor or registrar restores patient as next | `qr_queue.restore_entry_to_next` | Sets `priority = 1`; queue update event | Explicit recovery path |
| `cancelled` | `waiting` | Doctor or registrar restores patient as next | `qr_queue.restore_entry_to_next` | Sets `priority = 1`; queue update event | Uses British spelling here |
| `called` | `diagnostics` | Doctor sends patient to diagnostics | `qr_queue` diagnostics handler | Sets `diagnostics_started_at` | Allowed from `called` or `in_service` |
| `in_service` | `diagnostics` | Doctor sends patient to diagnostics | `qr_queue` diagnostics handler | Sets `diagnostics_started_at` | `in_service` exists in model and filters, but not all flows write it |
| `called` | `incomplete` | Doctor closes as incomplete | `qr_queue.mark_entry_incomplete` | Stores `incomplete_reason` | Allowed from `called`, `in_service`, `diagnostics` |
| `in_service` | `incomplete` | Doctor closes as incomplete | `qr_queue.mark_entry_incomplete` | Stores `incomplete_reason` | Same issue: `in_service` is modeled but not consistently emitted |
| `diagnostics` | `incomplete` | Doctor closes as incomplete | `qr_queue.mark_entry_incomplete` | Stores `incomplete_reason` | Explicit in code |
| `called` | `in_progress` | Doctor starts visit | `doctor_integration` start-visit handler | Creates or finds visit | Drift: queue row uses `in_progress`, not `in_service` |
| `any linked active queue row` | `canceled` | Visit is canceled | `visits.set_status` raw SQL update | Visit timestamps updated in same request | American spelling; bypasses queue service |
| `any linked active queue row` | `rescheduled` | Visit is rescheduled | `visits.reschedule_visit`, `visits.reschedule_visit_tomorrow` raw SQL update | Visit date changes in same request | `rescheduled` is not present in model comment |
| `queue entry fallback path` | `served` | Doctor completes queue-driven visit by queue entry id | `doctor_integration.complete_patient_visit` fallback branch | Visit may be created/updated to `completed`; billing side effects may occur | Only one explicit `served` writer found in runtime path |

## Read-Model State Usage

Different modules use different subsets of states:

| Area | Statuses treated as active / visible |
|---|---|
| Duplicate checks and queue limits | `waiting`, `called` |
| Reorder API | `waiting`, `called` |
| Queue position listing | `waiting`, `called`, `in_service`, `diagnostics` |
| Session reuse | `waiting`, `called`, `in_service` |
| Doctor dashboard stats | `waiting`, `called`, `served` |
| Queue statistics in `queue_service` | `waiting`, `called`, `completed`, `cancelled` |
| Legacy `OnlineDay` queue | `waiting`, `serving`, `done` |

## Observed Problems

1. There is no single canonical terminal state:
   - queue code uses `served`
   - stats code still counts `completed`
2. There is no single canonical "patient is now with doctor" state:
   - model and filters use `in_service`
   - doctor flow writes `in_progress`
3. Cancellation spelling is split:
   - model comment and some handlers use `cancelled`
   - visit and online-queue-new paths write `canceled`
4. Rescheduling is a queue state in router SQL, but not part of the model comment or central transition rules.
5. There is no central `validate_status_transition` implementation even though the SSOT service already reserves that method.

## Proposed Canonical Interpretation for Wave 2C

Wave 2C should adopt a single internal state machine and treat current drift values as aliases until migration is complete.

Recommended internal states:

- `waiting`
- `called`
- `in_service`
- `diagnostics`
- `served`
- `incomplete`
- `no_show`
- `cancelled`
- `rescheduled` (only if queue rows remain after visit move)

Recommended alias mapping during migration:

- `in_progress` -> `in_service`
- `completed` -> `served` for queue rows only
- `canceled` -> `cancelled`

## Stop/Go Guidance

Do not refactor queue mutation handlers until the project agrees on:

- canonical active states
- canonical terminal states
- whether `rescheduled` is a queue state or a visit-link marker
- how legacy `serving` / `done` maps to SSOT queue states
