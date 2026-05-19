# Telegram Bot Clinic Full Strategy

> Strategic implementation plan for Telegram in the clinic platform.
> This is a planning artifact for later backend/frontend execution slices; it does not contain secrets, bot tokens, or patient data.

## Summary

Telegram should be an operational layer for the clinic, not a full EMR. It should handle short notifications, simple confirmations, queue status, payment entry points, secure links, and human approval for AI-assisted workflows. Complex medical and administrative work stays in the protected web system or a future Telegram Mini App.

Patient bot v1 supports two patient-facing languages:

- `ru`: Russian
- `uz-Latn`: Uzbek Latin

Default language is Russian when no preference is saved. The staff/admin bot remains Russian-first in the initial strategy unless a later rollout explicitly adds staff localization.

## Implementation Status Legend

Use checkbox state as the implementation contract:

- [x] Implemented and backed by a current runtime path or testable contract.
- [ ] Not implemented yet, or only present as design text, placeholder, legacy helper, or disconnected UI.
- [ ] Partially closed items stay unchecked at the parent level until every required child item is complete; completed child items are checked below them.
- [ ] Needs verification means the behavior may exist, but it has not yet been confirmed against the canonical runtime path and targeted validation.

Status updates must name the canonical runtime file or test that justifies a checked item. Do not mark a Telegram feature complete from overview docs, stale reports, or legacy helper files alone.

## Current Implementation Snapshot

Current evidence to re-check before changing runtime behavior:

- patient bot runtime: `backend/app/api/v1/endpoints/telegram_webhook.py`
- staff/admin Telegram contracts and management: `backend/app/api/v1/endpoints/admin_telegram.py`
- ticket QR/start token generation and consumption: `backend/app/services/visit_confirmation_service.py`
- Telegram notification endpoints: `backend/app/api/v1/endpoints/telegram_notifications.py`
- bot adapter and command registration: `backend/app/services/telegram_bot.py`
- current focused tests: `backend/tests/unit/test_telegram_webhook_security.py`, `backend/tests/unit/test_visit_confirmation_service.py`, `backend/tests/unit/test_queue_position_notifications_telegram.py`, `backend/tests/unit/test_queue_time_window.py`, `backend/tests/unit/test_telegram_staff_read_only_menu_runtime.py`, `backend/tests/unit/test_telegram_staff_bot_token_runtime_config.py`, `backend/tests/unit/test_telegram_bot_management_api_service.py`, `backend/tests/unit/test_telegram_notifications_privacy.py`, `frontend/src/routing/__tests__/routeContract.test.js`

Partially closed areas as of the latest static audit:

- Patient bot MVP is closed for the Phase 1 backend slice: notification consent is shown after successful contact or QR/start patient linking, the full start -> language -> link -> consent path has targeted test coverage, the canonical notification sender has a tested safe patient Telegram event mapping helper, and appointment reminders now use the linked-patient Telegram event path when `db` and `patient_id` are provided.
- QR queue Phase 2 is closed for the current backend/security slice: linking, status reads, sensitive QR/start token TTL, event-driven next/called Telegram notifications, queue ordering/`queue_time` refresh validation, and expired/malformed/replayed/consumed token rollout checks are present.
- Payments can show status/debt summaries, send confirmation-style notifications, emit a safe patient Telegram unpaid bill notification from payment invoice creation, link the patient `/payments` bot reply to the protected `/patient/payments` app route, send safe patient Telegram `payment_paid` updates after successful provider webhook visit/appointment integration, and expose read-only staff reconciliation alerts for the supported Click/PayMe/Kaspi provider inventory. Public provider callbacks and internal demo routes must not be used as Telegram entry buttons.
- Staff bot has role-based read-only menus, authorization, token separation, hash-only confirmation request storage, hash-only idempotency binding for confirmation requests, confirmation-request audit, and denied-action audit, but confirmed state-changing action execution remains disabled by design until domain adapters and explicit action enablement are added.
- Telegram Mini App and AI approval flows are still planning items, not implemented runtime flows.

## Product Model

Use two separate Telegram bots.

Patient bot:

- appointment and visit notifications
- queue status and QR queue deep links
- payment notifications and payment links
- ready-result notifications with secure delivery policy
- support and clinic contact actions
- future Mini App entry points for full appointment booking, forms, payments, and patient cabinet

Staff/admin bot:

- registrar queue actions
- doctor schedule and next-patient notifications
- cashier payment alerts and reconciliation hints
- lab result readiness alerts
- owner/admin daily summaries, operational warnings, and integration errors
- AI approval interface for suggestions that need human confirmation

Telegram must not expose internal identifiers or medical implementation details to patients. Patient-facing text must avoid terms such as `EMR`, `visit_id`, `invoice_id`, `branch_id`, and raw database identifiers.

## Patient Bot Flow

`/start` onboarding:

- show language choice: `Русский` and `O'zbekcha`
- save selected language on the Telegram account or active Telegram session
- request Telegram phone contact
- accept the contact only when `contact.user_id` matches the sender
- link Telegram to an existing patient profile by trusted phone or one-time signed start token
- show notification consent
- open the localized main menu

Localized main menu:

- `Моя очередь` / queue status
- `Мои визиты` / current and upcoming visits
- `Оплата` / current debt and payment entry points
- `Результаты` / ready results and protected access
- `Помощь` / clinic support
- `Настройки` / language and notification preferences

QR queue flow:

- receipt or in-clinic QR opens `https://t.me/<patient_bot>?start=<one_time_signed_token>`
- token resolves server-side to queue/visit context
- token is short-lived and one-time-use
- bot shows queue number, cabinet, status, position if safely calculable, and refresh/support actions
- queue fairness and `queue_time` are never changed by status reads

Payments:

- Telegram shows short payment notifications and links into the approved payment flow
- payment providers remain PayMe, Click, Kaspi, or the existing application payment layer
- Telegram can show amount, status, and generic service label, but detailed invoices remain in the protected app
- paid/completed payments trigger short confirmation and receipt availability notice

Results:

- Telegram should not send diagnoses, full medical details, or raw EMR content in plain chat
- preferred long-term behavior is a secure link or Mini App protected view
- if PDF delivery is enabled for a specific slice, it must be restricted to linked patients, ready/finalized reports only, with delivery logged and no PDF content stored in logs

## Staff/Admin Bot Flow

Role-based menus:

- registrar: queue, next patient, find patient, redirect, payment status
- doctor: schedule, next patient, open EMR, call patient, incomplete EMR reminders
- cashier: unpaid invoices, paid invoices, refunds, payment reconciliation
- lab: ready reports, pending reports, result notification status
- owner/admin: daily report, revenue, doctor load, average wait, integration errors

Staff actions that change operational state require explicit confirmation:

- call or skip patient
- cancel or move visit
- change payment state
- issue refund
- close EMR or publish medical document
- change doctor schedule

Every staff action through Telegram must be checked against the application role system and recorded in audit logs.

## Architecture

Recommended backend flow:

```text
Telegram update
-> webhook or polling transport
-> Telegram bot service/router
-> patient/staff linking and authorization
-> domain services
-> notification service
-> Telegram adapter
-> TelegramMessage / notification log / audit log
```

Transport rules:

- polling remains valid before a public domain/server is ready
- webhook can be added later without changing bot business logic
- webhook and polling must call the same patient/staff bot handler
- transport code should not contain queue, payment, EMR, or report business logic

Notification architecture:

- business modules emit events such as `VisitCreated`, `QueueTicketIssued`, `QueueStatusChanged`, `PatientCalled`, `PaymentCreated`, `PaymentPaid`, `LabResultReady`, `EMRCompleted`, and `ReportGenerated`
- notification service maps events to channels and templates
- Telegram adapter sends localized messages from stable template keys
- SMS, email, WhatsApp, and push can be added later without rewriting domain modules

Localization architecture:

- patient-facing templates use stable keys and per-language text
- supported patient languages in v1 are exactly `ru` and `uz-Latn`
- language preference belongs to Telegram account/session and can later sync to patient profile preferences
- if language is missing, invalid, or unsupported, use Russian

Mini App architecture:

- future Mini App handles rich flows: appointment booking, patient forms, payment details, patient cabinet, and protected reports
- server validates Telegram Mini App `initData` before trusting identity
- Mini App links must be scoped to the linked patient or authenticated staff user

## Security Rules

Identity and linking:

- never trust Telegram `user_id` alone as a patient or staff identity
- link through one-time signed token, verified contact phone, admin confirmation, or protected cabinet link
- reject forwarded or spoofed contacts when Telegram `contact.user_id` does not match the sender

Deep links:

- contain only short opaque signed tokens
- expire quickly, typically 5 to 15 minutes for QR/start flows
- are one-time-use where they grant linking or sensitive access
- never expose `patient_id`, phone, diagnosis, `doctor_id`, `invoice_id`, or other internal identifiers in open text

Medical data:

- plain Telegram messages must not contain full diagnoses, complaints, prescriptions, medical histories, or complete lab values
- safe text format is: `Результаты готовы. Откройте защищенный кабинет.`
- unsafe text format is sending clinical findings directly into chat

Staff operations:

- every staff action checks role permissions server-side
- every state-changing staff action is logged with actor, action, target, timestamp, and result
- critical actions require confirmation buttons and must be idempotent

Secrets and logging:

- bot tokens stay in environment/config storage, never in code, tests, logs, or docs
- Telegram logs store message metadata and template keys, not medical document content
- failures log error type/status, not raw payloads with personal or medical data

## AI Through Telegram

Telegram can be used as an approval and notification surface for AI workflows, not as an autonomous medical decision-maker.

Doctor examples:

- AI prepared a draft conclusion
- doctor opens protected EMR, edits, accepts, or rejects
- acceptance/rejection is captured as feedback for future workflow quality

Admin examples:

- AI notices queue overload, payment anomalies, or integration failures
- bot sends concise alert and links to the protected dashboard
- admin confirms actions such as notifying registrar or opening the queue view

Owner examples:

- daily AI summary with revenue, average wait, overloaded services, unpaid visits, and integration health
- details remain in the dashboard, not in Telegram chat

AI workflow engines such as LangGraph orchestrate steps; they do not train the model by themselves. Adaptation requires feedback loops, RAG, historical decisions, and explicit accepted/rejected outcomes.

## Checkbox Rollout Roadmap

### Phase 1: Patient bot MVP with language choice

- [x] Status: Phase 1 patient bot MVP backend slice is complete. Additional notification types continue in later phase-specific slices.
- [x] `/start` entrypoint exists for the patient bot.
- [x] Patient-facing language set is exactly `ru` and `uz-Latn`, with Russian fallback.
- [x] Language selection can be saved for the Telegram account/session.
- [x] Telegram contact linking rejects spoofed contacts when `contact.user_id` does not match the sender.
- [x] Linked patient profile status can be shown without medical details.
- [x] Current queue status can be shown without changing queue fairness or `queue_time`.
- [x] Current visit summary can be shown without exposing internal identifiers.
- [x] Current payment/debt summary can be shown.
- [x] Show notification consent as part of onboarding after contact or QR/start patient linking, not only later from settings/menu.
- [x] Map basic patient business event names to safe Telegram messages through the canonical notification sender path.
- [x] Wire the first real notification call-site to the patient Telegram event helper: appointment reminders with `db` and `patient_id`.
- [x] Add a patient `/menu` refresh command that redraws the localized main menu without being intercepted by the staff menu guard: `backend/app/api/v1/endpoints/telegram_webhook.py` handles `/menu` and `backend/tests/unit/test_telegram_webhook_security.py::TestTelegramWebhookSecurity::test_menu_command_refreshes_patient_main_menu_without_staff_intercept` covers the patient path.
- [x] Expose the visible patient service aliases in Telegram's native command menu: `backend/app/services/telegram_bot.py` now registers `/services`, `/forms`, `/documents`, `/doctors`, and `/cabinet` in both Russian and Uzbek `setMyCommands` payloads, while `backend/tests/unit/test_telegram_webhook_security.py::TestTelegramWebhookSecurity::test_telegram_bot_service_registers_patient_commands` keeps the exact command registry covered. These aliases still route to safe placeholder/protected-entry guidance until the protected Mini App flows below are complete.
- [x] Add or confirm targeted tests for the completed onboarding path: start -> language -> contact/token link -> consent -> localized main menu.
- [x] Keep full appointment booking out of plain chat unless routed to the future protected Mini App or protected web app.

### Phase 2: QR queue

- [x] Status: Phase 2 QR queue backend/security slice is complete for the current rollout checklist.
- [x] One-time signed QR/start token exists.
- [x] QR/start token resolves server-side to queue/visit/patient context.
- [x] Token does not expose raw patient, visit, queue, doctor, or branch identifiers in open text.
- [x] Token consumption is one-time-use for sensitive linking.
- [x] Bot can show queue number, cabinet, and status when safely available.
- [x] Bot can show position/status refresh without mutating queue state.
- [x] Align sensitive QR/start token expiry with the security target of 5 to 15 minutes: `QueueBusinessService.assign_queue_token()` now caps legacy `expires_hours` input to a 5-15 minute runtime TTL and exposes `ttl_minutes` metadata.
- [x] Wire `QueueStatusChanged` and `PatientCalled` style events to Telegram next/called notifications: `QueuePositionNotificationService` maps `queue_position` to `QueueStatusChanged` and `queue_call` to `PatientCalled`, with focused coverage in `backend/tests/unit/test_queue_position_notifications_telegram.py`.
- [x] Add targeted validation that status refresh never changes queue ordering, fairness, or `queue_time`: `backend/tests/unit/test_telegram_webhook_security.py::TestTelegramWebhookSecurity::test_queue_status_refresh_preserves_ordering_and_queue_time`.
- [x] Add a rollout check for expired, replayed, malformed, and already-consumed QR tokens: `backend/tests/unit/test_visit_confirmation_service.py` covers expired/malformed parser rejection, expired stored token rejection, and consume-once replay blocking; `backend/tests/unit/test_telegram_webhook_security.py::TestTelegramWebhookSecurity::test_ticket_qr_link_new_user_prompts_notification_consent` keeps the live webhook link path covered.

### Phase 3: Payments

- [x] Status: complete for the current payment provider inventory. Read-only summaries, confirmation-style notifications, unpaid bill Telegram notification from payment invoice creation, protected app payment entry, safe protected receipt/payment URL replacement, direct webhook button regression coverage, safe provider webhook `payment_paid` patient Telegram updates, and read-only staff reconciliation alerts for Click/PayMe/Kaspi are verified.
- [x] Telegram can show current amount/debt/payment summary for a linked patient.
- [x] Telegram notification templates/endpoints can express payment confirmation and receipt availability.
- [x] Emit unpaid bill notifications from the canonical billing/payment event path: `PaymentInvoiceService.create_invoice()` emits a safe patient Telegram `payment_created` event for linked patient invoices, with focused coverage in `backend/tests/unit/test_payment_invoice_service.py`.
- [x] Add a payment entry button that links only to the approved payment flow or protected app.
  - [x] Audit current candidate routes before adding the button: `frontend/src/routing/routeRegistry.js` exposes `/payment/success` and `/payment/cancel` as public provider callbacks, `/internal-demo/payment-test` as an internal demo, and `/patient` is not a clearly approved patient payment entry contract for Telegram.
  - [x] Define the protected patient payment entry route contract: `frontend/src/routing/routeRegistry.js` registers role-scoped `/patient/payments`, `frontend/src/routing/routeSelectors.js` exposes `getProtectedPatientPaymentEntryPath()`, and `backend/app/api/v1/endpoints/admin_telegram.py` publishes `patient_payments_protected_entry`.
  - [x] Add the Telegram button after the protected route contract exists: `backend/app/api/v1/endpoints/telegram_webhook.py` sends an inline URL button built from `FRONTEND_URL + /patient/payments` and does not add invoice/payment/patient identifiers to the URL.
  - [x] Remove raw visit identifiers from the Telegram payment summary by showing only the count of linked visits in `backend/app/api/v1/endpoints/telegram_webhook.py`.
  - [x] Add a direct regression test that the webhook `/payments` reply markup uses `/patient/payments` and does not include invoice, payment, patient, or visit identifiers: `backend/tests/unit/test_telegram_webhook_security.py::TestTelegramWebhookSecurity::test_payments_command_sends_protected_entry_button_without_internal_ids`.
- [x] Replace placeholder receipt/payment URLs with real protected routes or provider-approved links: `backend/app/api/v1/endpoints/telegram_notifications.py` now builds receipt links from `settings.FRONTEND_URL + PATIENT_PAYMENT_ENTRY_ROUTE`, with focused privacy coverage in `backend/tests/unit/test_telegram_notifications_privacy.py`.
- [x] Wire payment status updates from payment reconciliation or transaction events to Telegram notifications: `backend/app/services/visit_payment_integration.py` now emits best-effort patient Telegram `payment_paid` events after successful provider webhook visit/appointment payment integration, with metadata limited to safe `amount`, `currency`, `status`, and `provider` values.
- [x] Add PayMe reconciliation alerts for staff if PayMe remains a supported provider in this clinic rollout: `PaymentReconciliationService.SUPPORTED_RECONCILIATION_PROVIDERS` includes `payme`, `PaymentReconciliationApiService.get_reconciliation_alerts()` feeds the staff Telegram `reconciliation_alerts` read-only menu, and `backend/tests/unit/test_telegram_staff_read_only_menu_runtime.py::TestTelegramStaffReadOnlyMenuRuntime::test_staff_reconciliation_alerts_menu_item_returns_safe_aggregate` verifies the safe staff summary.
- [x] Add Click reconciliation alerts for staff if Click remains a supported provider in this clinic rollout: `PaymentReconciliationService.SUPPORTED_RECONCILIATION_PROVIDERS` includes `click`, reconciliation alerts preserve provider names without raw transaction details, and `backend/tests/unit/test_payment_reconciliation_service.py::TestPaymentReconciliationService::test_alerts_include_supported_provider_names_for_staff_summary` covers the provider alert path.
- [x] Explicitly remove Apelsin from the supported reconciliation provider list because the application payment layer exposes Click, PayMe, and Kaspi settings/runtime paths, not Apelsin; `backend/tests/unit/test_payment_reconciliation_service.py::TestPaymentReconciliationService::test_supported_reconciliation_providers_match_runtime_inventory` guards the inventory.
- [x] Keep Kaspi covered as the supported non-Apelsin third provider: `PaymentReconciliationService.SUPPORTED_RECONCILIATION_PROVIDERS` includes `kaspi`, and the staff Telegram reconciliation aggregate lists supported providers without internal transaction identifiers.
- [x] Add tests proving Telegram messages expose only safe amount/status/service labels and no raw invoice/internal IDs: `backend/tests/unit/test_visit_payment_integration_service.py::TestVisitPaymentIntegrationService::test_process_payment_for_existing_visit_sends_safe_patient_telegram_status` checks emitted Telegram metadata, and `backend/tests/unit/test_notifications_push_logging.py::PatientTelegramEventMessagesTest::test_patient_telegram_payment_messages_redact_internal_identifiers` keeps rendered payment messages redacted.

### Phase 4: Staff bot

- [ ] Status: partially closed. Staff bot read-only operations, pre-mutation confirmation requests, hash-only idempotency binding for replay protection, the required confirmed/completed/failed audit event contract, queue adapter readiness metadata, queue `/call` + `/skip` domain adapter methods, and `/cancel_visit` + `/move_visit` queue-link adapter methods are implemented; confirmed state-changing actions remain disabled until full visit/payment/schedule domain mutation adapters and explicit action enablement are complete.
- [x] Role-based read-only menus exist for registrar, doctor, cashier, lab, admin, and owner/admin style users.
- [x] Staff bot token is configured separately from the patient bot token.
- [x] Staff linking is protected by server-side token validation.
- [x] Staff commands check role/authorization server-side.
- [x] Audit exists for staff link creation, rejected link tokens, received staff commands, and denied staff actions.
- [x] Runtime guard blocks Telegram execution of state-changing staff commands until domain adapters and explicit action enablement are implemented.
- [x] Add confirmation request flow for each state-changing action before mutation: `backend/app/api/v1/endpoints/telegram_webhook.py` now creates a hash-only `TelegramStaffConfirmationToken`, hash-only idempotency binding, and `staff_action_confirmation_requested` audit event for allowed state-changing staff commands, while keeping Telegram execution and domain mutation disabled; focused coverage is in `backend/tests/unit/test_telegram_staff_read_only_menu_runtime.py::TestTelegramStaffReadOnlyMenuRuntime::test_staff_state_change_command_requests_confirmation_without_mutation`.
- [x] Add idempotency keys or equivalent replay protection for confirmed staff actions: confirmation requests now persist `staff_action_idempotency:*` hash-only bindings, expose `idempotency_request_hash_runtime_enabled` in the staff bot contract, keep raw idempotency material out of Telegram/audit output, and rely on `TelegramStaffConfirmationTokenService.consume_for_confirmation(...)` single-use checks for future confirmed-action replay protection.
- [ ] Add domain service adapters for confirmed queue actions: call patient, skip patient, cancel/move visit.
  - [x] `/call` and `/skip` queue-domain adapter methods are available in `backend/app/services/queue_service.py` as `QueueBusinessService.staff_call_next_patient(...)` and `QueueBusinessService.staff_skip_queue_entry(...)`; focused coverage in `backend/tests/unit/test_queue_time_window.py` verifies server-side selection/status updates preserve `queue_time`.
  - [x] Staff bot contract now marks the `/call` + `/skip` queue adapter runtime as available while keeping `explicit_action_enablement` blocked in `backend/app/api/v1/endpoints/admin_telegram.py`.
  - [x] `/cancel_visit` and `/move_visit` queue-link adapter methods are available in `backend/app/services/queue_service.py` as `QueueBusinessService.staff_cancel_visit_queue_link(...)` and `QueueBusinessService.staff_move_visit_queue_link(...)`; focused coverage verifies queue entry status changes preserve `queue_time`.
  - [ ] Full protected visit-record mutation remains pending: the current `/cancel_visit` + `/move_visit` adapter scope is queue-link status only, with `visit_record_mutation_adapter` still blocked before Telegram action enablement.
- [ ] Add domain service adapters for confirmed payment actions: status change, refund where policy allows it.
- [ ] Add domain service adapters for confirmed schedule actions.
- [ ] Add remaining audit events for confirmed, failed, and completed state-changing actions; confirmation-requested audit is implemented with `staff_action_confirmation_requested`, and the required future event taxonomy is published as `staff_action_confirmed`, `staff_action_completed`, and `staff_action_failed` in `backend/app/api/v1/endpoints/admin_telegram.py`, but action execution is still disabled.
- [ ] Enable state-changing actions one by one behind explicit configuration and tests.
- [ ] Add negative tests for unauthorized staff, stale confirmations, repeated confirmations, and cross-role action attempts.
  - [x] Unauthorized/cross-role state-changing command denial is covered by `backend/tests/unit/test_telegram_staff_read_only_menu_runtime.py::TestTelegramStaffReadOnlyMenuRuntime::test_staff_state_change_command_denies_unauthorized_role`.
  - [x] Storage/service-level stale and repeated confirmation protection is covered by `backend/tests/unit/test_telegram_bot_management_api_service.py::TestTelegramBotManagementApiService::test_staff_confirmation_token_service_rejects_expired_record_without_consuming` and `backend/tests/unit/test_telegram_bot_management_api_service.py::TestTelegramBotManagementApiService::test_staff_confirmation_token_service_consumes_record_once`.
  - [x] Runtime confirmation callbacks remain inert while state-changing execution is disabled: `backend/tests/unit/test_telegram_staff_read_only_menu_runtime.py::TestTelegramStaffReadOnlyMenuRuntime::test_staff_queue_confirmation_callback_is_ignored_until_execution_enabled` proves no queue mutation, token consumption, or confirmed/completed/failed audit event is produced.
  - [ ] Webhook/runtime stale and repeated confirmation execution tests remain pending until confirmed action execution is enabled.

### Phase 5: Telegram Mini App

- [ ] Status: not implemented. Legacy `WebAppInfo` links do not count as completion without protected Mini App identity validation and scoped runtime flows.
- [x] Validate Telegram Mini App `initData` server-side before trusting identity: `backend/app/services/telegram_mini_app_init_data.py` validates the Telegram Mini App HMAC data-check string, rejects forged hashes and stale/future `auth_date` values, and is covered by `backend/tests/unit/test_telegram_mini_app_init_data.py`.
- [x] Scope Mini App sessions to the linked patient or authenticated staff user: `backend/app/services/telegram_mini_app_init_data.py` resolves validated `initData` only through existing active `telegram_users` links, returns explicit patient/staff scopes, rejects direct URL or unlinked identity, blocks inactive staff links, and `backend/tests/unit/test_telegram_mini_app_init_data.py` covers wrong-patient scope rejection.
- [ ] Implement appointment booking inside the protected Mini App flow.
  - [x] First backend-only booking policy slice: `backend/app/services/telegram_mini_app_init_data.py` builds a non-mutating safe appointment draft only from linked patient Mini App scope, forces scheduled/cash/UZS defaults, rejects staff scope, wrong patient scope, past dates, and invalid times, with focused coverage in `backend/tests/unit/test_telegram_mini_app_init_data.py`.
  - [x] Backend preview response contract: `backend/app/services/telegram_mini_app_init_data.py` now wraps the patient-scoped booking draft in a preview-only Mini App payload with mutation disabled, no appointment id, and no payment provider/transaction/webhook values, with focused coverage in `backend/tests/unit/test_telegram_mini_app_init_data.py`.
  - [x] Backend preview API slice: `POST /api/v1/telegram/mini-app/appointments/preview` in `backend/app/api/v1/endpoints/telegram_webhook.py` validates Mini App `initData`, resolves linked patient scope, returns the preview-only payload, rejects forged/staff access, handles missing bot-token and invalid booking-field errors, and is covered by `backend/tests/unit/test_telegram_webhook_security.py`.
  - [x] Backend create API slice: `POST /api/v1/telegram/mini-app/appointments` in `backend/app/api/v1/endpoints/telegram_webhook.py` reuses the trusted preview guard, rejects occupied doctor time slots, creates one safe scheduled/cash/UZS appointment through existing appointment CRUD, and is covered by `backend/tests/unit/test_telegram_webhook_security.py`.
  - [x] Patient `/book` command is now wired to return a protected booking entry button when a patient is linked and `FRONTEND_URL` is configured, with runtime implemented in `backend/app/api/v1/endpoints/telegram_webhook.py` and verification in `backend/tests/unit/test_telegram_webhook_security.py::TestTelegramWebhookSecurity::test_book_command_returns_localized_safe_booking_entrypoint`.
  - [x] Connect `/book` entry to a dedicated protected booking UI route instead of `/patient/payments`; implemented via `PATIENT_BOOKING_ENTRY_ROUTE = "/patient/bookings"` in `backend/app/api/v1/endpoints/admin_telegram.py`, with route registered in `frontend/src/routing/routeRegistry.js` as `patient-booking-entry` and used in `routeSelectors`/entrypoint contract.
- [x] Add protected patient section entry buttons for `/forms`, `/documents`, `/doctors`, and `/cabinet` to return `https://<frontend>/patient?tab=<section>` for linked patients.
  - [x] Add safe fallback for those commands when `FRONTEND_URL` is not configured: response reverts to service menu with unchanged placeholder template IDs and coverage in `backend/tests/unit/test_telegram_webhook_security.py`.
  - [ ] Implement patient forms inside the protected Mini App flow.
  - [x] Add backend protected forms preview/schema endpoint: `POST /api/v1/telegram/mini-app/forms/preview` validates Telegram Mini App `initData`, resolves linked patient scope, rejects forged/staff/wrong-patient access, returns non-mutating patient intake form metadata, and keeps storage disabled until capture/edit persistence is implemented; focused coverage is in `backend/tests/unit/test_telegram_webhook_security.py`.
  - [x] Route `/patient?tab=forms` to a dedicated patient section view (`frontend/src/pages/PatientPanel.jsx`) so the Telegram button lands on a separate functional screen instead of the generic patient home.
  - [ ] Add patient forms capture/edit flow in Mini App runtime with linked-patient validation.
- [ ] Implement patient cabinet inside the protected Mini App flow.
- [ ] Implement payment details inside the protected Mini App flow.
- [ ] Implement protected result/report viewing inside the Mini App flow.
- [x] Add tests for forged `initData`, expired auth, wrong patient scope, and direct URL access without Telegram identity: `backend/tests/unit/test_telegram_mini_app_init_data.py` covers `hash_mismatch`, `auth_date_expired`, `patient_scope_mismatch`, and missing Telegram `user` identity rejection.

### Phase 6: AI assistant approval flows

- [ ] Status: not implemented as Telegram approval runtime. Read-only summaries do not count as AI approval workflows.
- [ ] Add doctor draft review notification that links to protected EMR, not plain-chat medical content.
- [ ] Capture doctor accepted/rejected outcome for AI draft feedback.
- [ ] Add queue overload suggestion alerts for admin/registrar with protected dashboard links.
- [ ] Add payment anomaly alerts for cashier/admin with protected dashboard links.
- [ ] Add owner daily AI summary with safe high-level operational metrics only.
- [ ] Capture accepted/rejected admin outcomes for future workflow quality.
- [ ] Ensure AI workflow orchestration cannot autonomously mutate medical, queue, payment, or schedule state without human confirmation.
- [ ] Add tests for no diagnosis/full EMR leakage in AI Telegram messages.

## Continuous Plan Improvement Automation

Use this loop after every Telegram implementation slice:

- [ ] Before editing runtime code, read this plan plus the canonical runtime/test files named in Current Implementation Snapshot.
- [ ] For each implementation slice, copy the relevant unchecked roadmap item into the task brief as the explicit target.
- [ ] After implementation, update the checkbox state in this file in the same patch or PR.
- [ ] A checked item must cite or be traceable to a runtime file, migration if applicable, and targeted validation.
- [ ] If a feature is discovered in legacy or disconnected code, add a note under the matching phase instead of marking it complete.
- [ ] If validation exposes a narrower missing piece, replace the broad unchecked item with smaller checkboxes.
- [ ] Keep provider names, token TTL, identity rules, and supported language list synchronized with runtime configuration.
- [ ] When Telegram files change without this plan changing, treat that as a plan-drift warning during review.

Future automation backlog:

- [x] Add a lightweight repository check that warns when Telegram runtime files change without a corresponding update to this plan: `scripts/check_telegram_plan_drift.py` inspects changed Telegram runtime files, warns when this plan is absent, and supports `--fail-on-warning` for a later CI gate.
- [x] Add a script or CI job that prints all unchecked Telegram roadmap items for release review: `scripts/report_unchecked_telegram_plan_items.py` prints each unchecked checkbox with section path and line number via `python scripts/report_unchecked_telegram_plan_items.py`.
- [x] Add a plan drift check that flags stale provider names, unsupported language codes, and hardcoded placeholder URLs: `scripts/check_telegram_plan_content.py` warns on stale provider names, unsupported patient language codes, and placeholder/local URLs in this strategy plan, with `--fail-on-warning` available for a later CI gate.
- [x] Add a test inventory check that maps each checked roadmap item to at least one targeted test or smoke command: `scripts/report_telegram_plan_test_inventory.py` reports checked items with detected test/smoke evidence and can use `--fail-on-missing` once historical roadmap evidence is fully backfilled.
- [x] Add release-note generation from newly checked items so rollout evidence stays aligned with the plan: `scripts/report_telegram_plan_release_notes.py` compares checked roadmap items across refs or supplied plan files and prints release-note bullets for newly checked items.

## Acceptance Criteria

Plan artifact acceptance:

- [x] Plan exists at `.ai-factory/plans/telegram-bot-clinic-full-strategy.md`.
- [x] Patient bot v1 explicitly supports only Russian and Uzbek Latin.
- [x] The document names and integrates EMR, registrar, queue, QR queue, payments, notifications, reports, and AI.
- [x] Telegram is defined as an operational layer, not a medical record store.
- [x] Security section blocks sensitive medical data in plain Telegram messages.
- [x] QR/start links use one-time signed tokens and do not expose internal identifiers.
- [x] Roadmap is now sliced into backend, frontend, test, and rollout tasks with checkbox state.
- [x] Partially closed phases include completed subitems and open subitems.
- [x] Continuous plan improvement rules are documented.

Runtime acceptance still open:

- [x] Phase 1 is complete after the first real event-backed patient Telegram notification call-site is wired and verified.
- [x] Phase 2 is complete after expired/replayed/malformed/consumed token rollout checks are verified.
- [x] Phase 3 is complete after real payment entry and provider reconciliation alerts are verified.
- [ ] Phase 4 is complete after confirmed state-changing staff actions are enabled action by action with idempotency and audit.
- [ ] Phase 5 is complete after Mini App `initData` validation and protected patient flows are implemented.
- [ ] Phase 6 is complete after AI approval flows capture accepted/rejected outcomes without exposing medical details in plain chat.
