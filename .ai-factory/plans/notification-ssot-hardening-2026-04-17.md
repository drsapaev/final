# Implementation Plan: Notification SSOT Hardening

Created: 2026-04-17  
Mode: full  
Scope: mixed (backend + frontend + docs)

## Settings

- Testing: yes (targeted first, then regression)
- Logging: verbose
- Docs checkpoint: mandatory
- Runtime context: backend `18000`, frontend `5173`, staging Postgres `55432`

## Goal

Bring notification system to consistent SSOT behavior:
- all persistent business notifications are canonical backend events
- frontend role notification center fully matches backend catalog
- user preferences and anti-noise policies are actually enforced at runtime

## Canonical Contract Baseline

Persistent canonical event families to keep/finish:
- `all_free_*`
- `message_received`
- appointment/visit family (`appointment_reminder`, `appointment_confirmation`, `visit_confirmation`, `schedule_change`)
- payment/cashier family (`payment_notification`)
- queue family (`queue_update`, `queue_call`, `queue_position`, `queue_reminder`, `diagnostics_return_needed`, `queue_status_changed`)
- lab family (`lab_results`, `lab_critical_result`, `lab_new_study`, `lab_critical_finding`, `lab_result_sent_confirmation`)
- registrar/admin/system family (`new_appointment`, `price_change`, `system_alert`, `registrar_system_alert`, `security_alert`, `billing_alert`, `patient_registered`)

Non-inbox realtime only:
- typing/presence/read-receipt/reaction chat events

---

## Phase 0: Baseline Guardrails and Drift Inventory

- [ ] Freeze active event-type matrix in one contract note:
  - `.ai-factory/IMPLEMENTATION_NOTIFICATION_CATALOG_SSOT.md` (refresh to runtime truth)
- [ ] Build event inventory script/check that lists:
  - producer call-sites
  - canonical event types emitted
  - aliases used
- [ ] Mark legacy endpoints/services explicitly as:
  - canonical, adapter, or deprecated

Verification:
- [ ] run targeted inventory/unit checks for event contracts

---

## Phase 1: Event-Type and Alias Normalization

- [ ] Fix queue diagnostics type drift:
  - unify `diagnostics_return` into `diagnostics_return_needed` everywhere
- [ ] Resolve queue alias asymmetry (`queue_update`/`queue_changed`) with single canonical direction:
  - backend normalization
  - frontend alias map
  - websocket payload mapping
- [ ] Standardize deep-link resolution rules for mixed-role recipients:
  - fix `all_free_approved/rejected` recipient-specific targets

Verification:
- [ ] backend unit tests for normalize/alias behavior
- [ ] frontend unit tests for alias + routing target resolution

---

## Phase 2: Producer Wiring Completion (Business-Critical)

### 2.1 Cashier/Payment
- [ ] add canonical `payment_notification` producer in real payment lifecycle paths:
  - created/confirmed/failed/refunded/overdue transitions
- [ ] keep cashier WS as realtime adapter, not source of truth

### 2.2 Appointment/Visit Lifecycle
- [ ] wire canonical producers for:
  - reminder/confirmation/visit confirmation/schedule change
- [ ] normalize schedule updates via `schedule_change` + `change_type` metadata

### 2.3 Registrar Operational Events
- [ ] connect `RegistrarNotificationService` producers to active domain flows:
  - `new_appointment`, `price_change`, `queue_status_changed`, alert families

### 2.4 Lab Lifecycle Completion
- [ ] keep current `lab_results`, `lab_critical_result` producers
- [ ] add missing producers for declared types:
  - `lab_new_study`, `lab_critical_finding`, `lab_result_sent_confirmation`

Verification:
- [ ] targeted backend integration tests per family
- [ ] unread-count/inbox sync assertions for each wired family

---

## Phase 3: User Preferences Runtime Enforcement (Core UX)

- [ ] add centralized policy evaluation in canonical send path:
  - per-event-type + per-channel allow/deny
  - quiet hours handling
  - weekend suppression rules
  - severity break-through exceptions
- [ ] consolidate settings usage so runtime does not rely on legacy-only checks
- [ ] define and enforce channel fallback order by severity class

Policy baseline:
- critical (`security_alert`, `billing_alert`, `lab_critical_result`) can break through DND
- low-priority queue updates default to inbox-only in quiet hours

Verification:
- [ ] backend policy unit tests (matrix coverage)
- [ ] integration tests proving quiet-hours suppression and critical override

---

## Phase 4: Anti-noise Controls and UX Delivery Behavior

- [ ] add anti-noise guardrails:
  - burst dedup/grouping window for queue-family events
  - optional digest mode for low-priority informational events
- [ ] add explicit user controls:
  - mute/snooze duration
  - inbox-only mode (disable popups/toasts)
  - per-channel toggles aligned with backend policy model
- [ ] preserve existing read/seen/archive semantics

Verification:
- [ ] frontend unit tests for notification center behavior under throttled streams
- [ ] browser smoke for noisy scenarios (queue churn, message burst)

---

## Phase 5: Legacy/Mobile Convergence

- [ ] classify mobile notification endpoints:
  - migrate to canonical inbox model or mark deprecated with clear boundary
- [ ] remove ambiguous fallback logic in legacy notification read/status paths
- [ ] ensure no business-critical path depends on `NotificationHistory` as truth

Verification:
- [ ] targeted mobile API contract tests

---

## Phase 6: Docs, Runbook, and Verification Closure

- [ ] update docs:
  - canonical event catalog
  - role/type matrix
  - preference policy semantics
  - anti-noise escalation rules
- [ ] add operator-facing runbook for troubleshooting:
  - “event created but not visible”
  - “suppressed by policy”
  - “channel delivery failed”

Final verification order:
- [ ] targeted backend tests
- [ ] targeted frontend tests
- [ ] playwright user-facing smoke
- [ ] selected broader regression suite

---

## Acceptance Criteria

- all persistent business notifications are created via canonical platform
- frontend role matrix and backend emitted types are consistent
- user preference rules are enforced at delivery time, not only stored
- quiet-hours/anti-noise behavior is deterministic and test-covered
- legacy/mobile paths do not bypass canonical truth for business-critical events

## Blockers to Watch

- canonical vs legacy ambiguity during migration slices
- cross-role deep-link policy decisions
- flow ownership gaps in registrar/payment modules
- test coverage holes for queue/cashier/lab edge cases

## Next Execution Slice (recommended)

- Start with **Phase 1** (type/alias normalization), then **Phase 2.1** (payment producer wiring), then **Phase 3** (policy enforcement core).  
- This order removes visible drift first, then closes high-impact business gaps, then controls notification noise.

