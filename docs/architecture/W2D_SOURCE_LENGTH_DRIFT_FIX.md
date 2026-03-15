## Wave 2D Source Length Drift Fix

Date: 2026-03-10  
Mode: narrow Postgres schema/bootstrap drift fix

## Exact mismatch fixed

The `queue_entries.source` column in [online_queue.py](C:/final/backend/app/models/online_queue.py)
was declared as `String(20)`, but current runtime already creates queue entries
with `source="force_majeure_transfer"`.

- previous length: `20`
- required by current runtime: `22`
- chosen fix: `String(24)`

This keeps the field bounded while honestly fitting current legitimate values.

## Intended ownership

`queue_entries.source` is an existing provenance field for queue-entry creation
paths. The current legitimate values confirmed in active code/tests are:

- `online`
- `desk`
- `confirmation`
- `morning_assignment`
- `migration`
- `batch_update`
- `force_majeure_transfer`

`force_majeure_transfer` is not speculative. It is created directly in
[force_majeure_service.py](C:/final/backend/app/services/force_majeure_service.py)
as part of the current exceptional transfer flow.

## Why this is the narrowest honest fix

- It fixes one concrete Postgres blocker without changing queue behavior.
- It does not weaken integrity by switching to unbounded text.
- It does not introduce a broader enum/source-domain refactor.
- It is large enough for all currently confirmed queue-entry source values, but
  remains intentionally small and bounded.

## What this fix does not do

- does not touch `DailyQueue.specialist_id`
- does not change force-majeure semantics
- does not alter allocator logic
- does not address the remaining Postgres session/refresh issue
