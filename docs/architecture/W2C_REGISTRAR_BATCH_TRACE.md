# Wave 2C Registrar Batch Trace

Date: 2026-03-07
Mode: characterization-first, runtime trace
Scope: mounted registrar batch-only queue allocation

## Mounted Runtime Path

Observed runtime owner:

- `backend/app/api/v1/endpoints/registrar_integration.py::create_queue_entries_batch()`

Sequence:

1. API receives `POST /api/v1/registrar-integration/queue/entries/batch`.
2. Role gate allows only `Admin` / `Registrar`.
3. Router loads patient by `patient_id`.
4. Router iterates over `services[]`:
   - validates that each service exists
   - resolves `specialist_id`
   - if `specialist_id` matches `doctors.id`, converts it to `user_id`
   - otherwise accepts raw `users.id`
5. Router groups all services by resolved `specialist_id`.
6. For each grouped specialist:
   - loads `DailyQueue` for `specialist_id + today`
   - if absent, creates `DailyQueue` inline with `queue_tag=None`
7. Router performs duplicate pre-check:
   - same `patient_id`
   - same queue/day
   - statuses only `waiting` / `called`
8. If duplicate is found:
   - no allocator call
   - existing queue row is returned in the response
   - existing `number` and existing `queue_time` are reused
   - existing `source` is not changed
9. If duplicate is not found:
   - router calls `queue_service.create_queue_entry(...)`
   - `source` is taken from request
   - `queue_time` is set to one shared `current_time` captured once per batch
   - `auto_number=True` triggers internal `get_next_queue_number(...)`
   - `queue_service` also assigns `session_id` through `get_or_create_session_id(...)`
10. Router commits once after the specialist loop.
11. Response returns `success`, `entries[]`, `message`.

## Characterized Runtime Outcomes

### Successful creation

- new queue row is created with request `source`
- status is `waiting`
- number is assigned by legacy SSOT allocator
- response `queue_time` is serialized with timezone offset `+05:00`

### Repeated batch submission with same patient/queue/day

- if existing row is still `waiting`, second submission reuses it
- no new row is created
- original `source` remains unchanged

### Mixed-service batch with one existing active row

- existing `waiting` row for one specialist is reused
- a new row can still be created for a different specialist in the same batch

### Same specialist, different service `queue_tag`

- services are grouped by specialist, not by `queue_tag`
- same-specialist multi-service batch produces a single queue row

### Existing `diagnostics` row

- `diagnostics` is not treated as duplicate-blocking in mounted runtime
- a new `waiting` row is created in the same queue/day for the same patient

## Concurrency / Collision Observations

### Repeated request behavior

- repeated identical submission is effectively idempotent only for current
  `waiting/called` duplicate semantics

### Parallel duplicate read phase

- two parallel duplicate lookups can both observe `None` before any write
- this documents a read-before-write collision window
- this pass does not prove duplicate rows are committed in parallel, but it does
  prove the pre-check is not serialized

## Non-Runtime Duplicate Path

`backend/app/services/registrar_integration_api_service.py::create_queue_entries_batch()`
routes to `QueueBatchService`, but that path is not mounted in the current API
router. It is relevant as a migration seam, not as runtime truth.
