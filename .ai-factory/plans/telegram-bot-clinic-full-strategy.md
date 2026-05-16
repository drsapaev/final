# Telegram Bot Clinic Full Strategy

> Strategic implementation plan for Telegram in the clinic platform.
> This is a planning artifact for later backend/frontend execution slices; it does not contain secrets, bot tokens, or patient data.

## Summary

Telegram should be an operational layer for the clinic, not a full EMR. It should handle short notifications, simple confirmations, queue status, payment entry points, secure links, and human approval for AI-assisted workflows. Complex medical and administrative work stays in the protected web system or a future Telegram Mini App.

Patient bot v1 supports two patient-facing languages:

- `ru`: Russian
- `uz-Latn`: Uzbek Latin

Default language is Russian when no preference is saved. The staff/admin bot remains Russian-first in the initial strategy unless a later rollout explicitly adds staff localization.

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
- payment providers remain PayMe, Click, Apelsin, or the existing application payment layer
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

## Rollout Roadmap

Phase 1: Patient bot MVP with language choice

- `/start`
- Russian and Uzbek Latin onboarding
- contact-based linking
- patient profile status
- current queue status
- current visit/payment summary
- basic notifications

Phase 2: QR queue

- one-time signed QR/start token
- queue ticket linking
- queue number and cabinet
- position/status refresh
- next/called notifications

Phase 3: Payments

- unpaid bill notification
- payment entry button
- payment status update
- receipt availability notice
- PayMe/Click/Apelsin reconciliation alerts for staff

Phase 4: Staff bot

- role-based menus for registrar, doctor, cashier, lab, admin/owner
- server-side authorization
- audit logging
- confirmed queue/payment/schedule actions

Phase 5: Telegram Mini App

- appointment booking
- patient forms
- patient cabinet
- payment details
- protected result/report viewing
- Telegram `initData` validation

Phase 6: AI assistant approval flows

- doctor draft review
- queue overload suggestions
- payment anomaly alerts
- owner summaries
- feedback capture for accepted/rejected suggestions

## Acceptance Criteria

- Plan exists at `.ai-factory/plans/telegram-bot-clinic-full-strategy.md`.
- Patient bot v1 explicitly supports only Russian and Uzbek Latin.
- The document names and integrates EMR, registrar, queue, QR queue, payments, notifications, reports, and AI.
- Telegram is defined as an operational layer, not a medical record store.
- Security section blocks sensitive medical data in plain Telegram messages.
- QR/start links use one-time signed tokens and do not expose internal identifiers.
- Roadmap can be sliced into backend, frontend, test, and rollout tasks without product decisions left open.
