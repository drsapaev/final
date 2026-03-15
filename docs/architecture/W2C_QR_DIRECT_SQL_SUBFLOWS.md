# Wave 2C QR Direct SQL Subflows

Date: 2026-03-09
Mode: runtime characterization
Scope: production-relevant QR direct-SQL allocator subflows

## Runtime Family Split

### QR-SF-01: session bootstrap

- entry point: `POST /api/v1/queue/join/start`
- owner: `qr_queue.py::start_join_session()` -> `QRQueueService.start_join_session()`
- numbering step: none
- duplicate step: none
- queue entry creation: none
- source: not assigned yet
- queue_time: not assigned yet
- token/session handling: creates pending `QueueJoinSession`
- side effects: token validation, time-window info

This subflow is production-relevant, but it is not a direct-SQL allocator path.

### QR-SF-02: single-specialist QR join completion

- entry point: `POST /api/v1/queue/join/complete` without `specialist_ids`
- owner: `qr_queue.py::complete_join_session()` -> `QRQueueService.complete_join_session()`
- numbering step: delegated to `QueueDomainService.allocate_ticket(allocation_mode="join_with_token")`
- duplicate step: delegated to legacy queue service uniqueness rules through the boundary
- queue entry creation: delegated through boundary
- source: `online`
- queue_time: assigned by legacy allocator path
- token/session handling:
  - pending `QueueJoinSession` must exist
  - replay of same session after success returns `400`
- side effects:
  - session status flips to `joined`
  - queue.created websocket broadcast if non-duplicate

### QR-SF-03: clinic-wide / multi-specialist QR join completion

- entry point: `POST /api/v1/queue/join/complete` with `specialist_ids`
- owner: `qr_queue.py::complete_join_session()` -> `QRQueueService.complete_join_session_multiple()`
- numbering step: delegated per selected profile/specialist through boundary
- duplicate step: delegated per selected profile/specialist through boundary
- queue entry creation: delegated per selected profile/specialist through boundary
- source: `online`
- queue_time: shared response-level timestamp; per-entry queue_time assigned by legacy allocator
- token/session handling:
  - one pending session
  - clinic-wide token
  - selected IDs resolve via `QueueProfile` first if possible
- side effects:
  - multiple `queue.created` broadcasts
  - session marked `joined`

Characterized runtime detail:

- selected clinic-wide IDs map to `QueueProfile.id`
- resulting `DailyQueue.queue_tag` uses `QueueProfile.key`
- example observed values: `w2c_cardiology`, `w2c_lab`

### QR-SF-04: full-update first-fill QR additional-service branch

- entry point: `PUT /api/v1/queue/online-entry/{entry_id}/full-update`
- guard conditions:
  - `entry.source == "online"`
  - existing entry has queue_time
  - no previously found services for the patient
  - request contains one consultation plus one or more additional services
- numbering step:
  - consultation stays on original QR entry
  - each additional service creates an independent queue entry using raw SQL
    `MAX(number)+1` in target queue
- duplicate step:
  - no canonical duplicate gate before creating independent additional-service entry
- queue entry creation:
  - yes, one new `OnlineQueueEntry` per additional service / target queue
- source:
  - inherited from original entry via `entry.source or "online"`
- queue_time behavior:
  - consultation keeps original QR queue_time
  - independent additional-service entries get current local Tashkent time
- token/session handling:
  - no QR join session token here
  - `session_id` is still assigned via `get_or_create_session_id(...)`
- side effects:
  - may auto-create `DailyQueue` for missing `queue_tag`
  - creates Visit for QR patient
  - syncs patient data across related queue entries

### QR-SF-05: full-update edit-existing additional-service branch

- entry point: `PUT /api/v1/queue/online-entry/{entry_id}/full-update`
- guard conditions:
  - editing an already populated QR entry
  - `new_service_ids` contains additional services
- numbering step:
  - each additional service creates a new independent queue entry using raw SQL
    `MAX(number)+1` in the target queue
- duplicate step:
  - no canonical duplicate gate before creating independent additional-service entry
- queue entry creation:
  - yes, one new `OnlineQueueEntry` per new additional service / target queue
- source:
  - inherited from original entry via `entry.source or "online"`
- queue_time behavior:
  - original entry keeps original queue_time
  - new additional-service entries get current local Tashkent time
- token/session handling:
  - no QR join session token
  - `session_id` still assigned through `get_or_create_session_id(...)`
- side effects:
  - may auto-create target `DailyQueue`
  - new entry is independent (`visit_id=None`)
  - visit/patient sync continues in same endpoint

## Observed Characterization Outcomes

### Successful QR join

- single-specialist and clinic-wide joins succeed
- only one row is created for repeated same-day completion with the same phone
- replay of the exact same session token after success fails with `400`

### Direct-SQL first-fill behavior

- if first QR fill adds a second service in another queue, the route creates a new
  independent queue entry in that target queue
- observed number assignment was `8` when an existing target-queue row already had `7`
- new independent entry used current local time, not original QR queue_time

### Collision / replay observations

- two pending sessions for the same token + phone can both complete successfully and
  converge on one reused existing entry in the join flow
- direct-SQL full-update branches remain vulnerable to read-before-write style
  collision reasoning because numbering is still `MAX(number)+1` per queue
