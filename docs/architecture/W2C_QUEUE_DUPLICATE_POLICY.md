# Wave 2C Queue Duplicate Policy

Date: 2026-03-07
Mode: analysis-first, docs-only

## Executive Summary

Duplicate prevention is not centralized.

Different queue-entry creation flows use different identity keys and different
"active" status sets. That means queue-number allocation cannot be reviewed in
isolation from duplicate policy.

## Duplicate Checks Found

| File | Function / path | Duplicate key | Active statuses used | Source-specific behavior | Notes |
|---|---|---|---|---|---|
| `backend/app/services/queue_service.py` | `check_uniqueness()` | `phone` or `telegram_id` inside one `daily_queue` | `waiting`, `called` | Skips duplicate checks entirely for `desk` and `morning_assignment` | Main QR/online duplicate guard |
| `backend/app/services/queue_service.py` | `join_queue_with_token()` | Delegates to `check_uniqueness()` | `waiting`, `called` | `source` controls whether checks run | QR / online / telegram join path |
| `backend/app/api/v1/endpoints/registrar_integration.py` | `create_queue_entries_batch()` | patient in queue/day | `waiting`, `called` | Applies even for registrar-created rows in that path | Stronger than `check_uniqueness()` for patient identity, but separate |
| `backend/app/services/queue_batch_service.py` and repository | batch helper path | patient + queue/day | `waiting`, `called` | Source-aware request, but duplicate semantics are patient-based | Similar to registrar batch semantics |
| `backend/app/services/queue_session.py` | `get_or_create_session_id()` | `patient_id + queue_id + day` for session reuse | `waiting`, `called`, `in_service` | No source split | Session reuse active set is broader than duplicate prevention |
| `backend/app/services/online_queue.py` | legacy ticket issue / join identity bookkeeping | `phone::<phone>` or `tg::<telegram_id>` style keys in settings | Legacy day-open concepts, not SSOT statuses | Separate legacy rules | Not aligned with SSOT duplicate semantics |

## Observed Runtime Behavior

### Online / QR / Telegram joins

- Duplicate check runs by `phone` or `telegram_id`.
- Only `waiting` and `called` are considered active.
- `in_service`, `diagnostics`, `served`, `no_show`, and `cancelled` are not
  treated as blockers in this check.

### Desk / morning assignment

- `queue_service.check_uniqueness()` explicitly skips duplicate prevention for
  `desk` and `morning_assignment`.
- The business idea seems to be "trusted sources may create additional queue
  rows", but that is not encoded in one global policy document or one global
  helper.

### Registrar batch queue creation

- Patient identity becomes the main duplicate key.
- This is safer for visit-linked flows, but it is a different policy from the
  public join flow.

### Session reuse

- Session reuse treats `in_service` as active.
- Duplicate detection in QR/public join does not.
- That means two subsystems disagree on when the same queue membership is still
  "live".

## Practical Consequences

1. A patient can hit different duplicate outcomes depending on source.
2. Active-entry semantics are inconsistent across:
   - duplicate prevention
   - session reuse
   - fairness/position reads
3. Number allocation may appear safe for one source path and unsafe for another
   because the allocator is not the only gate to a new row.

## Rejoin Behavior

The codebase allows multiple re-entry patterns:

- public join may return an existing row if phone or telegram duplicate matches
- registrar and morning-assignment flows can create more rows because they are
  trusted sources or use a different duplicate check
- restore/reorder flows can move an existing row back into active ordering
  without allocating a new number

## Verdict

Duplicate policy is a domain rule, not an incidental validation.

`W2C-MS-005` would need a clear answer to all of the following before code
execution:

- what is the canonical duplicate identity for each source
- which statuses count as "active"
- whether trusted sources are allowed to bypass duplicates
- how session reuse relates to duplicate prevention

Without those answers, extracting number allocation alone would leave the
creation policy inconsistent.
