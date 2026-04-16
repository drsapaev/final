# Notification Catalog SSOT - Active Implementation Note

Updated: 2026-04-16  
Scope: Unified persistent inbox notifications (`/notifications/inbox`, `/notifications/unread-count`, WS sync) without new API surface.

## Canonical Catalog (Backend SSOT)

- `all_free_requested`
- `all_free_approved`
- `all_free_rejected`
- `message_received`
- `appointment_reminder`
- `appointment_confirmation`
- `visit_confirmation`
- `schedule_change`
- `payment_notification`
- `queue_update`
- `queue_call`
- `queue_position`
- `queue_reminder`
- `diagnostics_return_needed`
- `lab_results`
- `lab_critical_result`
- `lab_new_study`
- `lab_critical_finding`
- `lab_result_sent_confirmation`
- `prescription_ready`
- `new_appointment`
- `price_change`
- `queue_status_changed`
- `system_alert`
- `registrar_system_alert`
- `security_alert`
- `billing_alert`
- `patient_registered`

## Canonical vs Ephemeral

- Persistent inbox (SSOT): all catalog events above are backend-owned records via notification platform APIs.
- Ephemeral chat realtime only (non-inbox): typing, read receipts, presence, reaction updates.
- Alias normalization:
  - `result_ready` -> `lab_results`
  - `payment_update` -> `payment_notification`
  - `appointment_rescheduled` -> `schedule_change`
  - `queue_changed` -> `queue_update` on frontend normalization

## Producer Wiring Status

| Event family | Backend producer | Status |
|---|---|---|
| `all_free_*` | `backend/app/api/v1/endpoints/registrar_wizard.py` -> `notification_sender_service` | implemented |
| `message_received` | `backend/app/services/messages_api_service.py` | implemented |
| `lab_results`, `lab_critical_result`, `diagnostics_return_needed` | `backend/app/services/lab_notification_service.py` | implemented |
| registrar operational (`new_appointment`, `price_change`, `queue_status_changed`, alert family) | `backend/app/services/registrar_notification_service.py` | implemented |
| `patient_registered` (create only) | `backend/app/services/patient_service.py` | implemented |
| typed helper catalog (`lab_*`, queue family, registrar/admin family) | `backend/app/services/notifications.py` | implemented |

## Frontend Consumer Status

| Area | File | Status |
|---|---|---|
| role/type matrix + alias normalization | `frontend/src/contexts/NotificationCenterContext.jsx` | implemented |
| inbox open action routing by canonical type/deepLink | `frontend/src/components/notifications/NotificationInbox.jsx` | implemented |

## Routing Rules (Inbox Open)

- `all_free_*` -> `/admin/all-free-requests`
- `message_received` -> `/messages` (or `/messages?conversation=<id>` when metadata present)
- `lab_results` -> `/lab/results`
- `lab_critical_result` -> `/lab/results?critical=1`
- `new_appointment`, `price_change`, `queue_status_changed` -> `/registrar`
- `patient_registered` -> `/registrar/patients`
- queue family (`queue_call`, `queue_position`, `queue_reminder`, `queue_update`, `diagnostics_return_needed`) -> `/queue`
- `security_alert`, `billing_alert` -> `/admin`
- `registrar_system_alert` -> `/registrar`
- `system_alert` -> role-aware (`/admin` for admin, else `/registrar`)

## Validation Commands

Backend:
- `python -m py_compile backend/app/services/notifications.py`
- `python -m py_compile backend/app/services/lab_notification_service.py`
- `python -m py_compile backend/app/services/registrar_notification_service.py`
- `python -m py_compile backend/app/services/patient_service.py`
- `python -m pytest backend/tests/integration/test_notification_catalog_slice1.py backend/tests/unit/test_messages_notification_catalog_slice1.py -q`
- `python -m pytest backend/tests/unit/test_notification_platform_contract.py -q`

Frontend:
- `npx eslint src/contexts/NotificationCenterContext.jsx`
- `npx eslint src/components/notifications/NotificationInbox.jsx`
- `npx vitest run src/components/notifications/__tests__/NotificationInbox.test.jsx`
- `npx vitest run src/contexts/__tests__/NotificationCenterContext.test.jsx src/components/notifications/__tests__/RoleNotificationCenter.test.jsx src/__tests__/notificationGuardrails.test.js`
