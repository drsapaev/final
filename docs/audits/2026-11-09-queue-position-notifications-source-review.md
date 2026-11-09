# Queue position and patient notification — independent source Code Review (round 29)

**Date:** 2026-11-09  
**Repository:** `drsapaev/final`  
**Review base:** [`main` @ `a3506ffde854371a5f746584483bb61a608b4c21`](https://github.com/drsapaev/final/commit/a3506ffde854371a5f746584483bb61a608b4c21)  
**Mode:** docs-only, independent review; no application code, database, patient records, or configuration edited.  
**Prior audit continuation:** [merged PR #3892](https://github.com/drsapaev/final/pull/3892); previous history totals **138** source-observed candidates, including later groups [#6738450439](https://github.com/drsapaev/final/pull/3892#issuecomment-6738450439) and [#6739106445](https://github.com/drsapaev/final/pull/3892#issuecomment-6739106445). This document adds **five distinct candidates** to the *historical* total (now **143**), which does **not** indicate how many remain unresolved. No old findings copied as new.

## Executive summary

New candidates: **QPOSAUTH-BE-001 (P1), QPOSAUTH-BE-002 (P1/P2), QPOSCALL-BE-001 (P2), QPOSFAIR-BE-001 (P2), QPOSBATCH-BE-001 (P2).** Source-only review, not runtime proof. Fixes need explicit queue-domain owner policy, synthetic fail-first backend tests and an authorized fix PR. **Do not merge this audit as a claim fixes are implemented.**

### QPOSAUTH-BE-001 — P1: any authenticated user can enumerate the full queue through stats

**Evidence:** [`GET /queue/position/stats/queue/{queue_id}`](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/api/v1/endpoints/queue_position.py#L352-L382) requires only `get_current_user` and never checks role, linked patient identity, or queue ownership. It fetches the queue and [all visible entry rows](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/repositories/queue_position_api_repository.py#L85-L98), then returns [`QueuePositionNotificationService.get_queue_position_info`](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/services/queue_position_notifications.py#L419-L477) for *each*: queue-entry ID, queue number, status, priority, timestamps, queue tag, cabinet and specialist name. An unrelated logged-in patient can iterate numerical queue IDs and inspect other patients' *operational queue records*. **The response does not include patient name, diagnosis or phone by default; do not overclaim disclosure of those fields.**

**Synthetic red-first:** Create Patient A with their ticket in Queue Q1 and Patient B with Q2; logged in as A, call `/api/v1/queue/position/stats/queue/Q2`. Expect 403/404 or properly aggregate-only explicitly public data, not the detailed entry list. Verify Registrar/Admin intended access and doctor ownership rules; assert no patient labels/secrets are accidentally included. Use 2 separate queue IDs; do not mistake authentication for authorization.

**Repair direction:** explicit per-queue staff RBAC or patient-owned/aggregated status endpoint. Gate Doctor visibility against specialty and established owner policy. Avoid exposing internal entry IDs to unrelated patients.

### QPOSAUTH-BE-002 — P1/P2: owner guard is bypassed for queue entries with `patient_id=NULL`

**Evidence:** both [`GET /queue/position/{entry_id}`](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/api/v1/endpoints/queue_position.py#L111-L143) and [`GET /queue/position/by-number/{queue_number}`](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/api/v1/endpoints/queue_position.py#L145-L178) only run patient ownership verification when `entry.patient_id` is truthy. Non-staff users querying a queue-only/QR/legacy `OnlineQueueEntry` with `patient_id=None` **skip ownership checks entirely** and receive that row's queue position, status, priority, queue and cabinet metadata. QR join explicitly permits unlinked entries; absence of patient ID is not proof that any authenticated caller owns the ticket.

**Synthetic red-first:** Logged-in Patient A requests a synthetic unlinked entry `E.patient_id=NULL` by global ID and by queue number; require denied access unless a separate verified queue-session/claim capability authorizes the caller. Positive control for A's linked entry, negative for B's linked entry. No real patient IDs or sessions in tests.

**Repair direction:** fail closed for patient-role read when patient linkage is missing, or use a cryptographically bound session/ownership capability; role-independent generic 'staff' exceptions must be explicit and audited.

### QPOSCALL-BE-001 — P2: notification-only 'call patient' endpoint sends a false called message without validating queue state

**Evidence:** [`POST /queue/position/notify/call`](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/api/v1/endpoints/queue_position.py#L212-L238) loads an arbitrary entry, checks staff role/doctor scope, and calls [`notify_patient_called`](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/services/queue_position_notifications.py#L70-L112). Neither function verifies `entry.status == 'called'`, nor moves the entry into called state atomically. `notify_patient_called` always constructs a high-priority **“Вас вызывают!”** message and payload `status='called'`. A valid Registrar/Admin (or authorized doctor) can send it for a **waiting**, **no_show**, or **served** entry. This is not an anonymous access path; it is a misleading manual notification and workflow-state mismatch.

**Synthetic red-first:** For matching patient with a synthetic enabled push target, call endpoint on waiting and terminal tickets; assert 409/no delivery. For a genuinely called ticket, assert one delivered notification and no duplicate state transition. Test `cabinet_number` against canonical resource/doctor cabinet; currently the caller may supply arbitrary string, creating a second misleading message possibility.

**Repair direction:** status guard and auditable/manual resend semantics, with anti-duplicate policy; any new status transition belongs in the canonical queue service, not notification sender.

### QPOSFAIR-BE-001 — P2: positions undercount equal-timestamp or null-timestamp predecessors

**Evidence:** [`_count_people_ahead`](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/services/queue_position_notifications.py#L316-L334) counts a waiting predecessor only if it has greater priority or equal priority and **strictly smaller `queue_time`**. It lacks the queue's deterministic `id` tie-break and any `created_at` fallback. Meanwhile [canonical staff call-next ordering](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/services/queue_svc/_helpers.py#L84-L115) is priority descending, `coalesce(queue_time, created_at)` ascending, then `id` ascending. Two equal-priority waiting entries with identical `queue_time` therefore both report zero patients ahead, and a waiting entry with `queue_time=NULL` also ignores earlier peers with populated timestamps (SQL comparisons with NULL are unknown).

**Synthetic red-first:** Insert E1/E2 with identical timestamps but E1.id < E2.id; and E3 with `queue_time=NULL`/older `created_at`. Compare displayed `people_ahead` to canonical call-next ordering. Assert E2 reports at least one ahead and all positions reflect the same queue SSOT ordering; both queue-tag/resource and doctor-queue controls. Preserve priority fairness and original QR queue_time.

**Repair direction:** share one ordering predicate/rank query with call-next; include null fallback and deterministic id tie-break, avoiding divergent service-local queue logic.

### QPOSBATCH-BE-001 — P2: batch change notifications filter by numeric ticket instead of actual priority order

**Evidence:** [`notify_queue_changes_batch`](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/services/queue_position_notifications.py#L171-L248) restricts recipients to `OnlineQueueEntry.number > changed_after_number`, but decides actual position using [priority/queue_time](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/app/services/queue_position_notifications.py#L316-L334). Ticket numbers are not a serving rank after VIP/recovery priority changes. When a high-priority patient with number 6 is served, an ordinary waiting number 5 may move ahead even though `number <= changed_after_number=6` and is excluded from notification. Conversely numbers above the threshold can be re-notified when their position did not change.

**Synthetic red-first:** Q contains E5 number=5 priority=0, E6 number=6 priority=2, both waiting. Call/complete E6; trigger batch with `changed_after_number=6`. Assert E5 gets notified when and only when its actual `people_ahead` decreases, regardless of ticket number. Add a no-change control and provider failure response audit.

**Repair direction:** identify affected positions from before/after queue ordering (snapshot/event delta) or conservatively enumerate eligible waiting entries and compare stored last-notified rank; do not use printed number as a rank surrogate. Keep anti-noise thresholds and provider preferences.

## Validation and reproducibility

- **Executed:** connected GitHub source fetch, reference inspection of API/service/repository/queue service, inspection of existing [notification scope tests](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/tests/integration/test_queue_position_notify.py#L78-L141) and [unit service tests](https://github.com/drsapaev/final/blob/a3506ffde854371a5f746584483bb61a608b4c21/backend/tests/unit/test_queue_position_api_service.py#L1-L35); file Git blob SHAs matched `main` at the pinned review commit when review began.
- **Not executed:** pytest, disposable PostgreSQL concurrency tests, FastAPI TestClient replay, phone/Telegram/Push sends, web UI tests, lint/format/CI, runtime gate command or staging smoke tests. All five findings require runtime confirmation before any remediation claim.
- **Observed test coverage:** current integration tests verify a Doctor cannot notify another doctor's entry, but do not test patient self-read stats authorization, null patient linkage, false call status, fair tie-breaking or priority-driven batch notification.
- **Permitted file change:** *only this new Markdown audit document*. No changes allowed to app code, schema, migrations, secrets, tests, branches owned by others or production resources.
- **Gate:** risky-domain **queue RBAC/fairness** changes are NOT authorized in this audit PR. AGENTS.md requires an agent gate and synthetic tests before execution of fixes. The Windows PowerShell gate was not run from the connected GitHub-only environment; stop if asked to implement without a supported gate workflow.
- **Acceptance/stop conditions:** This PR documents source-backed findings; it does not imply production bugs reproduced. Stop on contradictory up-to-date code, existing findings with same root cause or missing authorization evidence. Determine prioritization and exact fixes with the owner; create separately approved scoped fix PRs with tests.
- **Rollback:** close this documentation-only PR or revert its single Markdown commit. It cannot affect production code or data.

## Reference

Prior review discussion with the original 27+111 historical findings: [PR #3892](https://github.com/drsapaev/final/pull/3892). This new PR begins a distinct audit cycle and is the location for future **new review comments**, without modifying that merged PR.
