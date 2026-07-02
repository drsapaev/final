# Dossier: Notification System Audit

Date: 2026-04-17  
Project: `C:\final`  
Runtime context: backend `18000`, frontend `5173`, staging Postgres `55432`

## 1) Executive Status

Overall maturity: **partially mature**.

- Canonical persistent inbox platform exists and is production-grade (`NotificationEvent`/`NotificationDelivery` + inbox/sync/ws contracts).
- Several business flows are already wired end-to-end (notably `all_free_*`, `message_received`, queue-position family, `patient_registered`).
- Significant partial zones remain: event-type drift, legacy mobile paths, non-uniform domain producer wiring, weak preference enforcement in runtime delivery.

## 2) Canonical SSOT Anchors

Primary backend SSOT:
- `backend/app/services/notification_platform_service.py`
- `backend/app/repositories/notification_platform_repository.py`
- `backend/app/models/notification.py` (`notification_events`, `notification_deliveries`)
- `backend/app/api/v1/endpoints/notifications.py`
- `backend/app/api/v1/endpoints/notification_websocket.py`

Primary frontend consumers:
- `frontend/src/contexts/NotificationCenterContext.jsx`
- `frontend/src/contexts/NotificationWebSocketContext.jsx`
- `frontend/src/components/notifications/NotificationInbox.jsx`
- `frontend/src/components/notifications/RoleNotificationCenter.jsx`

Settings surfaces:
- `backend/app/models/user_profile.py` (`UserNotificationSettings`)
- `backend/app/api/v1/endpoints/notifications.py` (`/notifications/settings/{user_id}`)
- `frontend/src/components/settings/NotificationPreferences.jsx`

## 3) What Is Implemented End-to-End Now

Confirmed end-to-end flows:
- `all_free_requested` (registrar cart -> admin inbox)
- `all_free_approved` / `all_free_rejected` (admin decision -> registrar/patient inbox)
- `message_received` (persisted message send -> recipient inbox + chat realtime)
- queue position family (`queue_call`, `queue_position`, `queue_reminder`) through queue-position API/service and inbox routing
- `patient_registered` on patient create flow

Delivery/state mechanics implemented:
- server-authoritative unread counts (`by_role`, `by_channel`, `by_severity`)
- state mutations: seen/read/archive/mark-all-read
- WebSocket sync/ack envelopes (`notification_sync_response`, `*_ack`)
- dedup keys at event and delivery levels

## 4) Partial / Incomplete Areas

### 4.1 Canonical Catalog Parity Gaps

- `diagnostics_return` vs `diagnostics_return_needed` drift:
  - queue producer emits `diagnostics_return`
  - canonical catalog/frontend role matrix expect `diagnostics_return_needed`
- queue alias asymmetry:
  - backend normalization maps `queue_update -> queue_changed`
  - frontend alias maps `queue_changed -> queue_update`
- `all_free_approved/rejected` deep-link mismatch for patient recipients (`/registrar` deep link from backend decision producer).

### 4.2 Producer Coverage Gaps

Defined but not clearly domain-wired from active endpoint/service paths:
- `new_appointment`, `price_change`, `queue_status_changed`, `registrar_system_alert`, `security_alert`, `billing_alert` (implemented in `RegistrarNotificationService`, but usage/call-sites are not broadly wired in domain flows).
- `schedule_change`, `appointment_confirmation`, `prescription_ready` helpers exist, but active producer call-sites are sparse or legacy.
- `lab_new_study`, `lab_critical_finding`, `lab_result_sent_confirmation` appear as allowed canonical types but without clear active producers.

### 4.3 Legacy/Parallel Paths

- Legacy notification history/settings models still coexist with canonical platform.
- Mobile notification endpoints/services use legacy semantics and contain TODO/uncertain logic comments.
- Some operational flows still broadcast via domain-specific WS channels (cashier/queue display) without canonical inbox event creation.

## 5) Missing (High-Value) Notification Coverage

## Must-have
- Payment/cashier lifecycle canonical events from real payment flows:
  - created/confirmed/failed/refunded/overdue
- Visit lifecycle canonicalization:
  - create/confirm/reschedule/cancel/no-show under consistent contract (`schedule_change` + `change_type`)
- Fix diagnostics-return event type drift (`diagnostics_return` -> canonical `diagnostics_return_needed`)
- Full producer-first migration for registrar operational alerts currently trapped in service-local paths

## Useful-next
- EMR lifecycle alerts:
  - note signed, plan changed, medication risk interaction, urgent follow-up required
- Integrity alerts:
  - doctor/profile/cabinet linkage mismatch
  - orphan patient-user links
  - queue/visit relation integrity anomalies
- Lab lifecycle completion for remaining declared canonical types

## Optional-later
- Digest/batching policies for low-priority event families
- Escalation chain by SLA (inbox -> push -> SMS)
- Intelligent grouping/collapse for queue burst events

## 6) User Notification Settings: Current Status

Already exists:
- Per-user channel/topic settings model and APIs
- UI for toggles + quiet hours + weekend preferences + reminder lead time

Partial:
- Settings are persisted but not consistently enforced by canonical delivery path
- Enforcement appears in selected legacy channel sends, not as central policy gate

Missing:
- Uniform server-side enforcement for:
  - quiet hours
  - weekend suppression
  - per-event-type channel policy
  - inbox-only vs realtime behavior
- User mute/snooze and do-not-disturb policy
- Unified policy model including Telegram channel preference in active SSOT

## 7) Anti-noise / Non-intrusive Controls Status

Implemented:
- Event/delivery dedup in backend platform
- Queue threshold notification gating in queue-position service
- Frontend cooldown logic around repeated sync/unread fetch
- Inbox state controls (read/seen/archive)

Missing:
- Severity-aware interrupt policy (what must break through vs inbox-only)
- Quiet-hours runtime enforcement
- Toast/popup throttling and burst suppression
- Role-targeted noise caps
- Policy-driven fallback/escalation without notification spam

## 8) Actionable Recommendation

Highest-value next step:
- Implement a **single server-side Notification Policy layer** inside canonical delivery flow (`NotificationPlatformService` integration point) that enforces:
  - per-event/per-channel preferences
  - quiet hours/weekend rules
  - severity break-through exceptions
  - anti-noise throttling/batching rules

Then converge producers (cashier/payment, visit lifecycle, registrar ops, remaining lab types) to canonical event creation so frontend and unread state are guaranteed consistent.

