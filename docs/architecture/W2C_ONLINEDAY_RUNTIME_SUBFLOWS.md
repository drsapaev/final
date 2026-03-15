# Wave 2C OnlineDay Runtime Subflows

Date: 2026-03-09
Mode: analysis-first, docs-only

## Summary

The `OnlineDay` family no longer participates in SSOT queue-entry creation.
Its mounted runtime is a small legacy island with one live counter-allocation
path and several admin/read surfaces around the same department/day counter
model.

## Runtime subflows

### OD-SF-01: Legacy day opening

- Entry point:
  - `POST /api/v1/appointments/open-day`
- Legacy object used:
  - `OnlineDay`
  - `Setting(category="queue")` for `open` and `start_number`
- Writes data:
  - Yes
- Affects numbering:
  - Indirectly, by setting the start-number baseline
- Affects duplicate behavior:
  - No
- Affects fairness/order:
  - Indirectly, only by controlling whether the morning window is open
- Affects production queue state:
  - Yes, but only inside the legacy island

### OD-SF-02: Legacy day closing

- Entry point:
  - `POST /api/v1/appointments/close`
- Legacy object used:
  - `OnlineDay.is_open`
- Writes data:
  - Yes
- Affects numbering:
  - No
- Affects duplicate behavior:
  - No
- Affects fairness/order:
  - No direct queue ordering effect
- Affects production queue state:
  - Yes, legacy morning-window state changes

### OD-SF-03: Legacy stats and board reads

- Entry points:
  - `GET /api/v1/appointments/stats`
  - `GET /api/v1/queues/stats`
  - `GET /api/v1/board/state`
- Legacy object used:
  - `OnlineDay`
  - `Setting(category="queue")` counters: `last_ticket`, `waiting`,
    `serving`, `done`
- Writes data:
  - No
- Affects numbering:
  - No, read-only
- Affects duplicate behavior:
  - No
- Affects fairness/order:
  - Reflects a legacy counter worldview that has no `queue_time`
- Affects production queue state:
  - No writes, but it is still production-visible

### OD-SF-04: Live legacy ticket issue

- Entry point:
  - `POST /api/v1/queues/next-ticket`
- Legacy object used:
  - `OnlineDay`
  - `Setting(category="queue")` `last_ticket` counter
- Writes data:
  - Yes
- Affects numbering:
  - Yes, increments legacy `last_ticket`
- Affects duplicate behavior:
  - No patient-level gate in this mounted path
- Affects fairness/order:
  - Yes, but only through legacy waiting counter semantics; no `queue_time`
- Affects production queue state:
  - Yes, this is the one live mounted allocator path in the OnlineDay family

### OD-SF-05: Disabled legacy self-join path

- Entry point:
  - `POST /api/v1/online-queue/join`
- Legacy object used:
  - `OnlineDay`
  - `Setting(category="queue")` counter and identity keys
- Writes data:
  - Would write if mounted
- Affects numbering:
  - Yes
- Affects duplicate behavior:
  - Yes, legacy phone / telegram memory
- Affects fairness/order:
  - Legacy counter-only worldview
- Affects production queue state:
  - No, because the router is currently disabled in `api.py`

## Subflow verdict

The OnlineDay family is not one broad active queue subsystem anymore.

Operationally it is:

- one live mounted write path (`/queues/next-ticket`)
- several mounted admin/read paths
- one disabled self-join path
- no runtime bridge into SSOT `DailyQueue` / `OnlineQueueEntry`
