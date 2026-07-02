# Wave 2C Queue Invariants

Date: 2026-03-06
Mode: analysis-first

## Purpose

These are the domain rules that already exist in code or are strongly implied by current behavior.
Any QueueDomainService must enforce them explicitly.

## Core Invariants

### 1. A queue entry must belong to a concrete daily queue

- Evidence:
  - `OnlineQueueEntry.queue_id -> DailyQueue.id`
  - `queue_service.create_queue_entry` requires `daily_queue` or `queue_id`
  - `morning_assignment.ensure_daily_queues_for_all_tags` pre-creates queues to avoid fallback behavior
- Meaning:
  - Queue lifecycle is anchored to `day + specialist + queue_tag`

### 2. Queue number allocation is monotonic within a queue

- Evidence:
  - `queue_service.calculate_next_number` uses `max(number) + 1` within the queue
  - `queue_service.get_next_queue_number` defaults to `scope="per_queue"`
- Meaning:
  - New numbers should only move forward in a queue
  - Reorder may change presentation order later, but ticket allocation is still monotonic

### 3. `queue_time` is the fairness timestamp

- Evidence:
  - `queue_service.create_queue_entry` sets `queue_time`
  - `registrar_integration.create_queue_entries_batch` explicitly says `queue_time = current time`
  - queue-position ordering uses `priority DESC`, then `queue_time ASC`
- Meaning:
  - Queue order should be based on registration time unless priority overrides it

### 4. Active-entry uniqueness is policy-dependent

- Evidence:
  - `queue_service.check_uniqueness` checks phone or telegram only for `waiting` and `called`
  - trusted sources `desk` and `morning_assignment` bypass duplicate prevention
  - `queue_batch_repository.find_existing_active_entry` also treats only `waiting` and `called` as active
- Meaning:
  - Duplicate prevention is not universal; it depends on source and status subset

### 5. Queue ordering is priority-first, then registration time

- Evidence:
  - `queue_position_notifications` counts people ahead using `priority DESC`, then `queue_time ASC`
  - `queue_position_api_repository.list_position_entries` uses the same ordering
  - `restore_entry_to_next` sets `priority = 1` to move a patient forward
- Meaning:
  - Number alone is not enough to determine current position

### 6. Session identity is stable for patient + queue + day

- Evidence:
  - `queue_session.get_or_create_session_id`
  - active session reuse applies to `waiting`, `called`, `in_service`
- Meaning:
  - Multiple services for one patient in the same queue/day should be grouped
  - Session lifecycle currently depends on the active-status definition

### 7. Queue capacity and online availability use a narrower active set

- Evidence:
  - `queue_service.check_queue_limits` counts only `waiting` and `called`
  - `queue_auto_close._count_queue_entries` also counts only `waiting` and `called`
- Meaning:
  - Capacity logic ignores `in_service`, `diagnostics`, `served`, and `incomplete`
  - This needs to stay explicit, not accidental

### 8. Visit lifecycle and queue lifecycle must stay coherent

- Evidence:
  - `visits.set_status` updates linked queue entries to `canceled`
  - `visits.reschedule_*` updates linked queue entries to `rescheduled`
  - `doctor_integration.complete_patient_visit` may update queue and visit together
- Meaning:
  - Queue and visit status changes are not independent
  - Transaction boundaries matter

### 9. Queue open/closed semantics are currently split

- Evidence:
  - SSOT queues use `DailyQueue.opened_at`
  - legacy appointments flow uses `OnlineDay.is_open` and `Setting(category="queue")`
- Meaning:
  - The system has two queue-open concepts today
  - Wave 2C must preserve this split until migration is planned explicitly

### 10. Queue taxonomy is shared policy, not presentation-only metadata

- Evidence:
  - `QueueProfile.queue_tags`
  - services and registrar flows depend on `queue_tag`
  - morning assignment pre-creates queues for all service queue tags
- Meaning:
  - Changing queue tag or profile mapping changes actual routing semantics

## Known Ambiguities and Weak Invariants

### Active-state definition is inconsistent

Current code uses different "active" subsets:

- `waiting`, `called`
- `waiting`, `called`, `in_service`
- `waiting`, `called`, `in_service`, `diagnostics`

This is the main reason queue behavior cannot be safely refactored without a domain model.

### State vocabulary is inconsistent

Observed drift:

- `cancelled` vs `canceled`
- `in_service` vs `in_progress`
- `served` vs `completed`
- `rescheduled` exists in runtime SQL but not in the model comment

### Transition validation is implicit

- `queue_service.validate_status_transition` exists but is not implemented
- Routers enforce local ad hoc transition rules instead

### Side effects are not isolated from transaction logic

- queue websocket/display notifications
- push notifications
- visit creation/update
- payment/billing decisions in doctor and registrar flows

These should not continue to live directly in router code.

## Required Guardrails Before Refactor

1. Freeze the canonical queue status set.
2. Freeze the definition of active entries for:
   - uniqueness
   - queue position
   - reorder
   - capacity
   - session reuse
3. Move queue/visit transition rules behind one service boundary.
4. Make post-commit side effects explicit.
