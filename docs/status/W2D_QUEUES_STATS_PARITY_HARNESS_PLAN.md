# W2D queues.stats parity harness plan

## Inputs
- `department`
- `date_str`

## Legacy path
- Mounted source of truth remains `GET /api/v1/queues/stats`
- Harness reads the same legacy semantics through `app.services.online_queue.load_stats(...)`

## Candidate SSOT path
- Internal comparison helper: [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py)
- Candidate data sources:
  - `DailyQueue`
  - `OnlineQueueEntry`
  - `QueueProfile.department_key -> queue_tags`
  - `Doctor.department`

## Strict parity fields
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Compatibility-only / deferred fields
- `is_open`
- `start_number`
- request echo fields like `department` / `date_str`

## Safety
- no route switch
- no mounted response change
- no OpenAPI change
- legacy mounted endpoint remains source of truth
- harness is internal/test-facing only
