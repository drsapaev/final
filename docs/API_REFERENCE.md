# 📚 API Reference - Clinic Management System

> **Base URL**: `http://localhost:8000/api/v1`  
> **Version**: 2.1.0  
> **Coverage**: Curated reference, not the full route inventory  
> **Authentication**: Bearer Token (JWT)  
> **Last Verified Slice**: 2026-03-14 (`Notifications`, `Settings`, `Authentication`, `Users`, `Queue`, `Payments`, `Analytics`, `Departments`, `Services`, `Doctors`, `Appointments`, `Patient Appointments (PWA)`, `Visits`, `Patients`, `Schedule`, `Health`, `Authentication Header`, `HTTP Status Codes`, `Roles & Permissions`, `New Modules`, `Links`, document framing)

> **Note**: Exact current route inventory lives in `/openapi.json`. This file is
> a curated high-level reference and may intentionally document only selected
> surfaces.

---

## 🔐 Authentication

This section is a curated overview of the main live auth surfaces. Exact route
inventory still lives in `/openapi.json`.

### POST `/auth/login`
OAuth2 password-form login endpoint used by the Bearer-token flow.

**Content type:** `application/x-www-form-urlencoded`

**Request fields:**
- `username`
- `password`
- optional OAuth2 fields: `scope`, `grant_type`, `client_id`, `client_secret`

**Response:**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

### GET `/auth/me`
Get the current authenticated user profile.

**Response:**
```json
{
  "id": 1,
  "username": "admin",
  "full_name": "Clinic Admin",
  "email": "admin@clinic.com",
  "role": "Admin",
  "is_active": true,
  "is_superuser": false
}
```

### POST `/authentication/login`
JSON login endpoint with refresh-token and 2FA-aware response.

**Request:**
```json
{
  "username": "admin",
  "password": "admin123",
  "remember_me": false,
  "device_fingerprint": "browser-abc123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 43200,
  "user": {
    "id": 1,
    "username": "admin",
    "role": "Admin"
  },
  "requires_2fa": false,
  "two_factor_method": null,
  "pending_2fa_token": null,
  "must_change_password": false
}
```

### POST `/authentication/refresh`
Refresh access and refresh tokens with a JSON body, not the `Authorization`
header.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOi..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 43200
}
```

### POST `/authentication/logout`
Logout the current session.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOi...",
  "logout_all_devices": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Выход выполнен успешно"
}
```

Additional live routes in this auth surface:

- `GET /authentication/status`
- `GET /authentication/sessions`
- `GET /authentication/profile`
- `PUT /authentication/profile`

---

## 👥 Users

Current-user profile is exposed via `/auth/me`. Inside the `/users` namespace,
the live self-service route is preferences, and the main management surface is
`/users/users*`.

### GET `/users/me/preferences`
Get preferences for the current authenticated user.

**Response example:**
```json
{
  "theme": "auto",
  "language": "ru",
  "compact_mode": false,
  "emr_smart_field_mode": "ghost",
  "emr_show_mode_switcher": true,
  "emr_debounce_ms": 500
}
```

### GET `/users/users`
List users. This is an authenticated route with pagination and filters.

**Query params:**
- `page` (int): Page number, default `1`
- `per_page` (int): Page size, default `20`, max `100`
- `role` (str): Optional role filter
- `status` (str): Optional status filter
- `is_active` (bool): Optional active flag filter
- `search` (str): Optional free-text search

**Response:**
```json
{
  "users": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@clinic.com",
      "role": "Admin",
      "is_active": true,
      "is_superuser": false
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20,
  "total_pages": 1
}
```

### POST `/users/users`
Create a new user. **Admin only.**

**Request:**
```json
{
  "username": "doctor1",
  "email": "doctor1@clinic.com",
  "password": "StrongPass123",
  "role": "Doctor",
  "phone": "+998901234567"
}
```

### GET `/users/users/{user_id}`
Get one user profile. Staff-only route.

### PUT `/users/users/{user_id}`
Update a user. **Admin only.**

### DELETE `/users/users/{user_id}`
Delete a user. **Admin only.**

**Query params:**
- `transfer_to` (int): Optional user id to transfer data before deletion

---

## 👤 Patients

This section is a curated map of the live `/patients*` surface. The current
contract is broader than the old mini-summary and now includes patient list and
CRUD, self-service patient portal reads, family relations, appointment helpers,
and soft-delete recovery routes.

All currently published `/patients*` routes are authenticated. Exact role gates
vary by operation, so use `/openapi.json` plus the live owner when a consumer
depends on stricter access assumptions.

### GET `/patients/`
List patients. Published query parameters: `skip`, `limit`, `q`, `phone`.

Query note:
- the old `search` query name in this document was stale
- the live owner now exposes general search through `q` and exact phone search
  through `phone`

### POST `/patients/`
Create a patient record.

### GET `/patients/{patient_id}`
### PUT `/patients/{patient_id}`
### DELETE `/patients/{patient_id}`
Read, update, or delete one patient record.

### GET `/patients/{patient_id}/appointments`
Authenticated helper for retrieving one patient’s appointments inside the
broader `/patients/*` surface.

### GET `/patients/{patient_id}/family`
### POST `/patients/{patient_id}/family`
### DELETE `/patients/{patient_id}/family/{relation_id}`
Family-relation helpers for viewing, adding, and removing patient relations.

### GET `/patients/{patient_id}/primary-contact`
Read the current primary contact for one patient.

### GET `/patients/deleted`
### DELETE `/patients/{patient_id}/soft`
### POST `/patients/{patient_id}/restore`
Soft-delete and recovery helpers for the patient registry.

Portal note:
- patient self-service appointment and results routes remain documented below in
  `Patient Appointments (PWA)`

---

## 📅 Patient Appointments (PWA)

This section is a curated map of the currently published patient portal
surface. The older `/patient/appointments*` summary is stale: the live
patient-facing contract is now published under `/patients/*`, and the current
OpenAPI only exposes read-style self-service routes here.

### GET `/patients/appointments`
Patient-scoped appointment list for the current authenticated patient.

Access note:
- the mounted owner requires the `Patient` role
- the current published OpenAPI does not expose the old `status_filter` or
  `include_past` query parameters

### GET `/patients/appointments/{appointment_id}`
Patient-scoped appointment details for the current authenticated patient.

### GET `/patients/results`
Patient-scoped lab-results list for the current authenticated patient.

### Adjacent route: GET `/patients/{patient_id}/appointments`
This is still a live authenticated helper under the broader `/patients/*`
family, but it is not the same self-service PWA route as
`GET /patients/appointments`.

Historical note:
- the old `cancel`, `reschedule`, and `available-slots` claims are not present
  in the current published patient-facing contract
- the nearest published `available-slots` route now lives under
  `/schedule/available-slots` and is a staff-facing schedule helper rather than
  a patient portal action

---

## 🏥 Visits

This section is a curated map of the live `/visits*` surface. The old
`/visits/` CRUD summary is stale: the current published contract is namespaced
under `/visits/visits*` and mixes public/tokenized reads with authenticated
mutation routes.

### GET `/visits/visits`
List visits. Published query parameters: `patient_id`, `doctor_id`, `status_q`,
`planned_date`, `limit`, `offset`.

Access note:
- the current published OpenAPI exposes this read route without a security
  block

### POST `/visits/visits`
Create a visit.

Request note:
- the current published create model is centered on `patient_id`, `doctor_id`,
  `notes`, `planned_date`, and optional `source`
- the older `service_ids` and `scheduled_at` example in this document was
  stale

### GET `/visits/visits/{visit_id}`
Get a visit card together with its service items.

Access note:
- the current published OpenAPI exposes this read route without a security
  block

### POST `/visits/visits/{visit_id}/services`
Add a service item to a visit.

### POST `/visits/visits/{visit_id}/status`
Change visit status. The current route takes `status_new` as a published query
parameter.

### POST `/visits/visits/{visit_id}/reschedule`
### POST `/visits/visits/{visit_id}/reschedule/tomorrow`
Reschedule helpers for moving a visit to a specific date or to tomorrow.

### GET `/visits/info/{token}`
Public token-based visit lookup.

Historical note:
- the old `PUT /visits/{id}` and `DELETE /visits/{id}` claims are not present
  in the current published contract

---

## 💳 Payments

This section is a curated map of the live payment surface. The current payment
contract is split across cashier payment creation, provider-init flows, public
provider discovery and webhooks, and reconciliation/reporting routes.

### GET `/payments/providers`
Public route that lists currently available payment providers.

**Response:**
```json
{
  "providers": [
    {
      "name": "Payme",
      "code": "payme",
      "supported_currencies": ["UZS"],
      "is_active": true,
      "features": {
        "refunds": true,
        "webhooks": true
      }
    }
  ]
}
```

### POST `/payments/init`
Initialize a provider-backed payment session.

Access note:
- current live owner requires `Admin`, `Registrar`, or `Cashier`

**Request:**
```json
{
  "visit_id": 1,
  "amount": 150000,
  "provider": "payme",
  "currency": "UZS",
  "description": "Consultation payment",
  "return_url": "https://app.example.com/payments/success",
  "cancel_url": "https://app.example.com/payments/cancel"
}
```

**Response:**
```json
{
  "success": true,
  "payment_id": 101,
  "provider_payment_id": "payme_abc123",
  "payment_url": "https://checkout.example.com/abc123",
  "status": "pending",
  "error_message": null
}
```

### POST `/payments/`
Create a cashier payment record.

Access note:
- current live owner requires `Admin` or `Cashier`

**Request:**
```json
{
  "visit_id": 1,
  "appointment_id": null,
  "amount": 150000,
  "currency": "UZS",
  "method": "cash",
  "note": "Paid at front desk"
}
```

Response note:
- generated OpenAPI currently exposes a free-form object for this operation, so
  exact response keys should be treated as implementation-backed

### GET `/payments/`
List payments with filters.

Access note:
- current live owner requires `Admin`, `Cashier`, `Registrar`, or `Doctor`

**Query params:**
- `visit_id` (int): Optional visit filter
- `date_from` (str): Optional start date `YYYY-MM-DD`
- `date_to` (str): Optional end date `YYYY-MM-DD`
- `limit` (int): Optional limit, default `50`
- `offset` (int): Optional offset, default `0`

**Response note:**
- the wrapper shape is stable as `{payments, total}`, but the individual
  payment items are intentionally flexible in generated schema

### GET `/payments/{payment_id}`
Get current payment status.

Access note:
- current live owner allows `Admin`, `Cashier`, `Registrar`, `Doctor`, and
  `Patient`

**Response:**
```json
{
  "payment_id": 101,
  "status": "paid",
  "amount": 150000,
  "currency": "UZS",
  "provider": "payme",
  "provider_payment_id": "payme_abc123",
  "created_at": "2026-03-14T09:00:00Z",
  "paid_at": "2026-03-14T09:05:00Z",
  "provider_data": {
    "transaction_id": "txn_001"
  }
}
```

### POST `/payments/{payment_id}/cancel`
Cancel a payment.

Access note:
- current live owner requires `Admin` or `Cashier`

### GET `/payments/{payment_id}/receipt`
Generate a receipt for an authenticated user.

**Query params:**
- `format_type` (str): Optional format, default `pdf`

### GET `/payments/{payment_id}/receipt/download`
Download a receipt file for an authenticated user.

### POST `/payments/invoice/create`
Create a payment invoice from the payment module.

**Request:**
```json
{
  "amount": 150000,
  "currency": "UZS",
  "provider": "click",
  "description": "Lab invoice",
  "patient_info": {
    "name": "Иван Иванов"
  }
}
```

### GET `/payments/invoices/pending`
List pending invoices for an authenticated user.

### Public provider webhooks
These webhook routes are public and are meant for provider callbacks, not
frontend clients:

- `POST /payments/webhook/payme`
- `POST /payments/webhook/click`
- `POST /payments/webhook/kaspi`

### Additional payment operations
Other active payment surfaces also exist under:

- `GET /payments/visit/{visit_id}`
- `POST /payments/test-init` (public diagnostic route)
- `/payments/reconcile/*`

---

## 📊 Analytics

This section is a curated map of the live analytics surface. The current
analytics contract is broader than the older “overview/payment providers”
summary and now spans core dashboard routes plus advanced, KPI, predictive,
export, visualization, AI, and wait-time families.

### GET `/analytics/quick-stats`
Get quick dashboard statistics.

Access note:
- current mounted owner checks the role set `admin`, `doctor`, `nurse`

Response note:
- generated OpenAPI currently exposes a free-form JSON response for this route

### GET `/analytics/dashboard`
Get dashboard data for the same core analytics role set.

Response note:
- generated OpenAPI currently exposes a free-form JSON response for this route

### GET `/analytics/trends`
Get trend analytics for the last `N` days.

Access note:
- current mounted owner checks the role set `admin`, `doctor`, `nurse`

**Query params:**
- `days` (int): Optional analysis period, default `30`, max `365`

### Advanced analytics family
Authenticated analytics routes also live under:

- `GET /analytics/advanced/kpi`
- `GET /analytics/advanced/doctors/performance`
- `GET /analytics/advanced/patients/advanced`
- `GET /analytics/advanced/revenue/advanced`
- `GET /analytics/advanced/predictive`
- `GET /analytics/advanced/comprehensive/advanced`

Public exception in this family:

- `GET /analytics/advanced/health`

### KPI and predictive families
Additional authenticated analytics routes also exist under:

- `/analytics/kpi-*`
- `/analytics/predictive/*`

These routes cover KPI metrics, KPI trends/comparison, forecasting, prediction
accuracy, and predictive scenario analysis.

### Export and visualization families
Authenticated analytics export and visualization routes also exist under:

- `/analytics/export/*`
- `/analytics/visualization/*`

Public exceptions in these families:

- `GET /analytics/export/health`
- `GET /analytics/visualization/health`

### AI analytics family
Authenticated AI analytics routes also exist under:

- `/analytics/ai/usage-analytics`
- `/analytics/ai/learning-insights`
- `/analytics/ai/cost-analysis`
- `/analytics/ai/function-performance/{function_name}`
- `/analytics/ai/model-comparison`
- `/analytics/ai/usage-summary`
- `/analytics/ai/track-usage`
- `/analytics/ai/optimize-models`
- `/analytics/ai/generate-training-dataset`

Role note:
- this family is authenticated, and some routes have tighter role gates than
  the core dashboard routes

### Wait-time analytics family
Staff-facing wait-time analytics routes also live under:

- `GET /analytics/wait-time/wait-time-analytics`
- `GET /analytics/wait-time/real-time-wait-estimates`
- `GET /analytics/wait-time/service-wait-analytics`
- `GET /analytics/wait-time/wait-time-summary`
- `GET /analytics/wait-time/wait-time-heatmap`
- `GET /analytics/wait-time/wait-time-comparison`

### Schema note
Most analytics routes currently return free-form JSON objects in generated
OpenAPI. Only some subfamilies, such as AI usage analytics and wait-time
analytics, publish stricter response schemas.

---

## 🏢 Departments

This section is a curated map of the currently published department lookup
surface. The live `/departments` contract is read-only in OpenAPI today; the
older create/update summary is stale.

### GET `/departments`
Authenticated department list route. Supports optional `active_only` filtering.

### GET `/departments/active`
Authenticated convenience route for active departments. The current published
schema still exposes the same optional `active_only` query flag here.

### GET `/departments/{department_id}`
Authenticated single-department lookup by ID.

---

## 🩺 Services

This section is a curated map of the current services catalog surface. The old
`/services/department/{dept_id}` summary is stale; the live contract is now
split between catalog CRUD, category management, and several SSOT helper
routes.

The current published OpenAPI exposes these service routes without a security
block, so exact access control should be verified against the live runtime if a
consumer depends on stricter assumptions.

### GET `/services`
List or search services. Published query parameters: `q`, `active`,
`category_id`, `department`, `limit`, `offset`.

### POST `/services`
Create a service entry. The published request model is `ServiceCreate`.

### GET `/services/{service_id}`
Fetch a single service.

### PUT `/services/{service_id}`
Update a service.

### DELETE `/services/{service_id}`
Delete a service.

### GET `/services/categories`
### POST `/services/categories`
List or create service categories. The current list route supports optional
`active` filtering.

### PUT `/services/categories/{category_id}`
### DELETE `/services/categories/{category_id}`
Update or remove a service category.

### GET `/services/code-mappings`
Return SSOT mapping data between service IDs and external/internal codes.

### GET `/services/queue-groups`
Return queue-group metadata used by adjacent queue-aware service flows.

### GET `/services/resolve`
Resolve a service by `service_id` or `code`.

### GET `/services/admin/doctors`
Return the auxiliary admin doctor list published alongside the services
surface.

---

## 👨‍⚕️ Doctors

This section is a curated map of the live doctor-related surface. The old
`/doctors/*` summary is stale: the current published contract splits doctor
lookup, doctor self-service, appointment-linked schedule lookups, and admin
management across multiple route families.

For new integrations, prefer `/doctor-info/*` for doctor lookup and
profile-style reads. Doctor self-service and queue/visit actions currently live
under `/doctor/*`, while admin management lives under `/admin/doctors*`.

### GET `/doctor-info/doctors`
Authenticated doctor lookup list with published filters:
`specialization`, `department_name`, `active_only`.

### GET `/doctor-info/doctors/{doctor_id}`
Authenticated single-doctor lookup by ID.

### GET `/doctor-info/doctors/by-user/{user_id}`
Authenticated helper route for resolving the doctor record by user ID.

### GET `/doctor-info/appointments/{appointment_id}/doctor-info`
Authenticated appointment-linked doctor/department lookup helper.

### GET `/appointments/doctor/{doctor_id}/schedule`
Authenticated doctor schedule lookup published inside the broader
`/appointments/*` family.

### `/doctor/*` route family
Published authenticated doctor self-service and workflow routes currently
include calendar, personal info, queue call/complete/start-visit actions, and
doctor-side visit helpers.

### `/admin/doctors*` route family
Published authenticated admin doctor-management routes currently include doctor
CRUD, doctor schedule management, department-doctor linking, and doctor stats.

---

## 📅 Appointments

This section is a curated map of the live operational `/appointments*`
surface. The current contract is broader than plain CRUD and now includes
schedule lookup, visit lifecycle, EMR/prescription subresources, payment-adjacent
helpers, and a small deprecated compatibility tail.

### GET `/appointments/`
List appointments. Published query parameters: `skip`, `limit`, `patient_id`,
`doctor_id`, `department`, `date_from`, `date_to`.

### POST `/appointments/`
Create an appointment.

### GET `/appointments/{appointment_id}`
### PUT `/appointments/{appointment_id}`
### DELETE `/appointments/{appointment_id}`
Fetch, update, or delete a single appointment.

### GET `/appointments/doctor/{doctor_id}/schedule`
### GET `/appointments/department/{department}/schedule`
Authenticated schedule lookup helpers for doctor and department calendars.

### POST `/appointments/{appointment_id}/start-visit`
### POST `/appointments/{appointment_id}/complete`
### GET `/appointments/{appointment_id}/status`
Appointment lifecycle routes for visit start, completion, and current status.

### GET `/appointments/{appointment_id}/emr`
### POST `/appointments/{appointment_id}/emr`
### POST `/appointments/{appointment_id}/emr/save`
Appointment-linked EMR read/write helpers.

### GET `/appointments/{appointment_id}/prescription`
### POST `/appointments/{appointment_id}/prescription`
### POST `/appointments/{appointment_id}/prescription/save`
Appointment-linked prescription read/write helpers.

### GET `/appointments/pending-payments`
Authenticated payment-adjacent helper for pending appointment or visit payment
worklists.

### POST `/appointments`
Distinct authenticated report-generation route published alongside the CRUD
surface. This is not the same operation as `POST /appointments/`.

### POST `/appointments/open-day`
### POST `/appointments/close`
Authenticated operational day-control routes. These are still live but are not
the safest first integration surface for new consumers.

### GET `/appointments/stats`
### GET `/appointments/qrcode`
Authenticated deprecated compatibility routes. Prefer newer surfaces where
available.

### POST `/appointments/{appointment_id}/mark-paid`
Published payment-adjacent helper on the appointment surface. The current
OpenAPI exposes this route without a security block, so consumers should verify
the live runtime contract before depending on stricter assumptions.

---

## 🗓️ Schedule

This section is a curated map of the live `/schedule*` helper surface. These
routes back staff-facing scheduling and availability workflows rather than the
patient portal itself.

All currently published `/schedule*` routes are authenticated. The live owner
uses a tighter role split than the old docs suggested: list/lookup helpers are
for `Admin`, `Registrar`, or `Doctor`, while create/delete operations are
admin-only.

### GET `/schedule`
List schedule templates. Published query parameters: `department`, `doctor_id`,
`weekday`, `active`, `limit`, `offset`.

### POST `/schedule`
Create a schedule template. The published request model is `ScheduleCreateIn`.

### DELETE `/schedule/{id}`
Delete a schedule template.

### GET `/schedule/weekly`
Weekly schedule helper with published filters `department`, `doctor_id`, and
`week_start`.

### GET `/schedule/daily`
Daily schedule helper with published parameters `date_str`, `department`, and
`doctor_id`.

### GET `/schedule/available-slots`
Available-slot helper with published parameters `date_str`, `department`, and
`doctor_id`.

### GET `/schedule/doctors`
Department-aware doctor list helper for scheduling UIs.

### GET `/schedule/departments`
Department list helper for scheduling UIs.

Portal note:
- this route family is the nearest live owner for the `available-slots`
  behavior referenced historically by older patient portal docs

---

## 📋 Queue

This section is a curated map of the live queue surface. The current queue
contract is split across modern `/queue/*` modules and legacy compatibility
routes under `/queue/legacy/*`.

For new integrations, prefer the session-based join flow and the public
position endpoints instead of the legacy `/queue/legacy/*` routes.

### GET `/queue/available-specialists`
Public route for QR-registration UIs to show currently available specialists.

### POST `/queue/join/start`
Start a public queue-join session from a QR token.

**Request:**
```json
{
  "token": "qr_token_abc123"
}
```

**Response:**
```json
{
  "session_token": "session_abc123",
  "expires_at": "2026-03-14T14:30:00Z",
  "queue_info": {
    "specialist_name": "Иванов И.И.",
    "department": "cardiology"
  }
}
```

### POST `/queue/join/complete`
Complete a public join session. Supports both single-specialist and
clinic-wide QR flows.

**Request:**
```json
{
  "session_token": "session_abc123",
  "patient_name": "Иван Иванов",
  "phone": "+998901234567",
  "telegram_id": 123456789,
  "specialist_ids": [12, 15]
}
```

Response note:
- runtime returns queue-placement data, but the generated OpenAPI schema is
  currently untyped for this operation, so exact response keys should be
  treated as implementation-backed rather than fully documented contract

### GET `/queue/position/{entry_id}`
Public route to check one queue entry position.

**Response:**
```json
{
  "entry_id": 101,
  "queue_number": 7,
  "status": "waiting",
  "people_ahead": 3,
  "priority": 0,
  "queue_time": "2026-03-14T09:30:00Z",
  "queue_info": {
    "specialist_name": "Иванов И.И."
  }
}
```

### GET `/queue/position/by-number/{queue_number}`
Public lookup by printed queue number.

**Query params:**
- `specialist_id` (int): Required specialist id

### GET `/queue/status/{specialist_id}`
Staff-facing queue snapshot for one specialist.

Access note:
- current live owner requires `Admin`, `Doctor`, or `Registrar`

**Query params:**
- `target_date` (str): Optional queue date in `YYYY-MM-DD`

### POST `/queue/{specialist_id}/call-next`
Call the next patient in a specialist queue.

Access note:
- current live owner requires `Admin`, `Doctor`, or `Registrar`

**Query params:**
- `target_date` (str): Optional queue date in `YYYY-MM-DD`

**Response:**
```json
{
  "success": true,
  "message": "Пациент вызван",
  "patient": {
    "id": 55,
    "queue_number": 7
  },
  "queue_length": 4
}
```

### Legacy compatibility routes
These routes still exist, but they are no longer the recommended queue
contract for new integrations:

- `POST /queue/legacy/join`
- `GET /queue/legacy/today`
- `POST /queue/legacy/call/{entry_id}`
- `GET /queue/legacy/statistics/{specialist_id}`

Additional active queue surfaces also exist under:

- `/queue/admin/*`
- `/queue/entry/*`
- `/queue/reorder/*`
- `/queue/position/notify/*`

---

---

## 🔔 Notifications

### GET `/notifications/settings/{user_id}`
Get notification settings for a specific user.

Access note:
- a user can read their own settings
- `Admin` can read any user's settings

**Response:**
```json
{
  "id": 10,
  "user_id": 1,
  "profile_id": 1,
  "email_appointment_reminder": true,
  "sms_appointment_reminder": false,
  "push_payment_receipt": true,
  "reminder_time_before": 60,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "08:00",
  "weekend_notifications": false,
  "created_at": "2026-03-14T09:00:00Z",
  "updated_at": "2026-03-14T09:00:00Z"
}
```

### PUT `/notifications/settings/{user_id}`
Update notification settings.

**Request:**
```json
{
  "email_appointment_reminder": true,
  "sms_appointment_reminder": false,
  "push_payment_receipt": true,
  "reminder_time_before": 30,
  "quiet_hours_start": "23:00",
  "quiet_hours_end": "07:00",
  "weekend_notifications": false
}
```

### GET `/notifications/history`
Get notification history. This is a staff-facing route, not a current-user-only
profile endpoint.

**Query params:**
- `skip`: Offset
- `limit`: Limit
- `recipient_id`: Filter by recipient id
- `recipient_type`: Filter by recipient type
- `notification_type`: Filter by notification type
- `status`: Filter by notification status

---

## ⚙️ Settings

### GET `/settings?category={category}`
Get settings for one category. **Admin only.**

Returns a list of `{category, key, value}` rows.

**Query params:**
- `category` (str): Required category key such as `printer`, `online_queue`, `display_board`
- `limit` (int): Optional limit, default 100
- `offset` (int): Optional offset, default 0

### PUT `/settings`
Upsert one setting row by `category` + `key`. **Admin only.**

**Request:**
```json
{
  "category": "display_board",
  "key": "brand",
  "value": "AI Factory Clinic"
}
```

**Response:**
```json
{
  "category": "display_board",
  "key": "brand",
  "value": "AI Factory Clinic"
}
```

---

## 🔔 Health

This section is a curated map of the currently published health-style routes
under the API base URL. The older root `/` health claim in this file was stale
for a `/api/v1`-scoped reference.

### GET `/health`
Public simple healthcheck plus DB probe from the live mounted health owner.

Published response note:
- current response shape is a small object like `{"ok": true, "db": "ok"}`
- the exact `db` value can degrade to an error-class string when the DB check
  fails

### GET `/status`
Public short server-status alias published alongside `/health`.

### Adjacent public health routes
Current published public health-style routes also include:
- `/authentication/health`
- `/analytics/advanced/health`
- `/analytics/export/health`
- `/analytics/visualization/health`
- `/mobile/health`
- `/2fa/health`

### Adjacent authenticated health routes
Current published authenticated health-style routes also include:
- `/system/monitoring/health`
- `/ai/v2/health`
- `/mcp/health`

This section stays curated on purpose: the repo now exposes multiple
subsystem-specific health endpoints rather than one global health contract.

---

## 🔑 Authentication Header

For HTTP endpoints that declare the published OpenAPI security scheme, send:

```text
Authorization: Bearer <access_token>
```

Current published scheme:
- `OAuth2PasswordBearer`
- OpenAPI password-flow `tokenUrl`: `/api/v1/auth/minimal-login`

Important notes:
- this file does not try to collapse all login/token issuance routes into one
  auth story; see the `Authentication` section above for the broader live split
  between `/auth/*` and `/authentication/*`
- not every published route is protected; current public examples include
  `/health`, several subsystem health routes, selected payment/webhook paths,
  and public queue lookups
- this section is about HTTP/OpenAPI auth headers only; websocket auth is a
  separate runtime surface

## 📝 HTTP Status Codes

This is a curated guide to common response patterns in the current API. It is
not an exhaustive per-route matrix.

| Code | Current meaning in this repo |
|------|------------------------------|
| 200 | Standard successful read/update/action response with a body |
| 201 | Resource created successfully on create-style routes |
| 204 | Successful no-body completion on selected delete-style operations |
| 401 | Missing or invalid bearer token on protected routes |
| 403 | Authenticated request rejected by `require_roles(...)` |
| 404 | Resource not found or own-data linkage missing on some scoped flows |
| 422 | Generated request/query/body validation error |
| 500 | Internal backend error fallback |

Additional note:
- `422` is the most common non-2xx response code in the current generated
  OpenAPI
- `202` and custom `400`/`409` style domain responses also exist, but they are
  route-specific and should be treated as endpoint-level contract details, not
  as the global baseline

## 🔒 Roles & Permissions

This section is a role glossary, not a full permission matrix. Exact access is
endpoint-specific and enforced by live `require_roles(...)` checks plus
superuser bypass.

| Role | Current high-level meaning |
|------|----------------------------|
| Admin | Broad admin and management surface |
| Registrar | Front-desk patient, appointment, and schedule workflows |
| Doctor | Clinical and doctor workflow surfaces |
| Cashier | Payment and cashier-adjacent surfaces |
| Lab | Lab-result and selected patient/lab workflows |
| Patient | Self-service portal routes for own data |

RBAC notes:
- current deterministic RBAC evidence is strongest for `Admin`, `Registrar`,
  `Doctor`, `Cashier`, and `Patient` via the backend role-routing checks
- `is_superuser=True` bypasses role checks in the current live security layer
- the live security layer normalizes `Receptionist` to `Registrar`
- specialty roles such as `cardio`, `derma`, and `dentist` still appear in the
  current codebase as compatibility/domain-specific doctor-adjacent roles
- use endpoint-specific sections, `/openapi.json`, and role-routing tests for
  exact access expectations instead of treating this table as a full matrix

---

## 🆕 New Modules

This footer section is a curated pointer map for newer or more specialized
route families. It is not a release-note ledger.

The old `v2.1.0` block was stale: it pointed to non-published
`/cardio/ecg/upload`, `/cardio/ecg/{id}/interpret`, `/dental/odontogram*`, and
`/messages/audio` routes that are not in the current generated contract.

### 💓 Cardiology helpers (`/cardio/*`)

Currently published cardio routes include:

- `GET /cardio/ecg`
- `POST /cardio/ecg`
- `GET /cardio/blood-tests`
- `POST /cardio/blood-tests`
- `GET /cardio/risk-assessment`

Drift note:
- AI-assisted ECG analysis exists, but it is currently published under the AI
  families (`/ai/ecg-interpret` and `/ai/v2/analyze-ecg`), not as
  `/cardio/ecg/{id}/interpret`

### 🦷 Dental helpers (`/dental/*`)

Currently published dental routes include:

- `GET/POST /dental/examinations`
- `GET/POST /dental/treatments`
- `GET/POST /dental/prosthetics`
- `GET /dental/xray`
- price-override workflow under:
  - `/dental/price-override`
  - `/dental/price-overrides`
  - `/dental/price-overrides/pending`
  - `/dental/price-override/{override_id}/approve`

Drift note:
- no live `/dental/odontogram*` family is currently published in
  `/openapi.json`

### 🎤 Messaging and voice (`/messages/*`)

Currently published messaging routes include:

- `POST /messages/send`
- `POST /messages/upload`
- `POST /messages/send-voice`
- `GET /messages/voice/{message_id}/stream`
- conversation, unread, reaction, read, and download helpers across the rest of
  `/messages/*`

WebSocket note:
- user-to-user chat is mounted separately at `/ws/chat`
- the old generic `/messages/audio` narrative was stale

### 📊 System monitoring (`/system/monitoring/*`)

Currently published monitoring routes include:

- `GET /system/monitoring/health`
- `GET /system/monitoring/metrics/system`
- `GET /system/monitoring/metrics/application`
- `GET /system/monitoring/metrics/history`
- `GET /system/monitoring/metrics/summary`
- `GET /system/monitoring/alerts`
- `GET/PUT /system/monitoring/thresholds`
- `POST /system/monitoring/collect`

Scope note:
- the mounted monitoring family is broader than the old five-route summary
- backup-management routes remain adjacent under `/system/backup/*`, but they
  are not part of this monitoring subsection

---

## 📖 Links

Canonical generated docs links:

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`

Custom in-app documentation helpers:

- `/api/v1/docs/api-docs`
- `/api/v1/docs/api-schema`
- `/api/v1/docs/endpoints-summary`

Custom-docs note:
- these `/api/v1/docs/*` pages are mounted and useful for navigation, but the
  generated `/docs` and `/openapi.json` remain the canonical contract sources

WebSocket note:
- WebSocket routes are not represented in `/openapi.json`
- current mounted families include `/ws/queue`, `/ws/chat`, `/ws/cashier`,
  `/api/v1/ws/notifications/connect`, and authenticated queue helpers under
  `/api/v1/ws-auth/*`
- do not hardcode the old placeholder host
  `wss://api.clinic.example.com/ws/`; use your deployed host plus the mounted
  path instead

