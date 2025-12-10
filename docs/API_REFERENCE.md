# 📚 API Reference - Clinic Management System

> **Base URL**: `http://localhost:8000/api/v1`  
> **Version**: 1.0.0  
> **Authentication**: Bearer Token (JWT)

---

## 🔐 Authentication

### POST `/authentication/login`
Login and get access token.

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 43200
}
```

### POST `/authentication/refresh`
Refresh access token.

**Headers:**
```
Authorization: Bearer <refresh_token>
```

### POST `/authentication/logout`
Logout and invalidate token.

---

## 👥 Users

### GET `/users/me`
Get current user info.

**Response:**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@clinic.com",
  "role": "Admin",
  "is_active": true
}
```

### GET `/users/users`
List all users. **Admin only.**

### POST `/users/users`
Create new user. **Admin only.**

---

## 👤 Patients

### GET `/patients/`
List patients with pagination.

**Query params:**
- `skip` (int): Offset, default 0
- `limit` (int): Limit, default 100
- `search` (str): Search by name/phone

### GET `/patients/{id}`
Get patient by ID.

### POST `/patients/`
Create new patient.

**Request:**
```json
{
  "first_name": "Иван",
  "last_name": "Иванов",
  "phone": "+998901234567",
  "birth_date": "1990-01-15",
  "gender": "male"
}
```

---

## 📅 Patient Appointments (PWA)

### GET `/patient/appointments`
Get current patient's appointments.

**Query params:**
- `status_filter` (str): Filter by status
- `include_past` (bool): Include past appointments

**Response:**
```json
[
  {
    "id": 1,
    "appointment_date": "2025-12-15",
    "appointment_time": "10:00",
    "doctor_name": "Иванов И.И.",
    "department": "cardiology",
    "department_name": "Кардиология",
    "status": "scheduled",
    "can_cancel": true,
    "can_reschedule": true,
    "hours_until_appointment": 48.5
  }
]
```

### GET `/patient/appointments/{id}`
Get single appointment details.

### POST `/patient/appointments/{id}/cancel`
Cancel appointment (24h limit).

**Response:**
```json
{
  "success": true,
  "message": "Запись успешно отменена",
  "appointment_id": 1
}
```

**Error (< 24h):**
```json
{
  "detail": "Отмена возможна минимум за 24 часа до приёма. До записи осталось 12.5 часов."
}
```

### POST `/patient/appointments/{id}/reschedule`
Reschedule appointment.

**Request:**
```json
{
  "new_date": "2025-12-20",
  "new_time": "14:00"
}
```

### GET `/patient/appointments/{id}/available-slots`
Get available slots for rescheduling.

**Query params:**
- `date_from` (str): Start date YYYY-MM-DD
- `date_to` (str): End date YYYY-MM-DD

### GET `/patient/results`
Get lab results for current patient.

---

## 🏥 Visits

### GET `/visits/`
List visits with filters.

**Query params:**
- `patient_id` (int): Filter by patient
- `doctor_id` (int): Filter by doctor
- `status` (str): Filter by status
- `date_from` (date): Start date
- `date_to` (date): End date

### POST `/visits/`
Create new visit.

**Request:**
```json
{
  "patient_id": 1,
  "doctor_id": 2,
  "service_ids": [1, 2],
  "scheduled_at": "2025-12-15T10:00:00",
  "notes": "Первичный осмотр"
}
```

### PUT `/visits/{id}`
Update visit.

### DELETE `/visits/{id}`
Delete visit.

---

## 💳 Payments

### GET `/payments/`
List payments.

### POST `/payments/`
Create payment.

**Request:**
```json
{
  "visit_id": 1,
  "amount": 150000,
  "provider": "payme",
  "discount_percent": 10
}
```

### POST `/payments/webhook/payme`
PayMe webhook handler.

### POST `/payments/webhook/click`
Click webhook handler.

---

## 📊 Analytics

### GET `/analytics/overview`
Get analytics overview.

### GET `/analytics/payment-providers`
Payment providers breakdown.

### GET `/analytics/appointment-flow`
Appointment flow analytics.

### GET `/analytics/revenue-breakdown`
Revenue breakdown by department.

---

## 🏢 Departments

### GET `/departments/`
List all departments.

### POST `/departments/`
Create department. **Admin only.**

### PUT `/departments/{id}`
Update department. **Admin only.**

---

## 🩺 Services

### GET `/services/`
List all services.

### GET `/services/department/{dept_id}`
Get services by department.

---

## 👨‍⚕️ Doctors

### GET `/doctors/`
List all doctors.

### GET `/doctors/{id}/schedule`
Get doctor's schedule.

### GET `/doctors/{id}/queue`
Get doctor's current queue.

---

## 📋 Queue

### GET `/queue/`
Get all queues.

### POST `/queue/join`
Join queue (online).

**Request:**
```json
{
  "patient_phone": "+998901234567",
  "patient_name": "Иван Иванов",
  "department": "cardiology",
  "priority": "normal"
}
```

### POST `/queue/{id}/call`
Call next patient.

### POST `/queue/{id}/complete`
Complete queue item.

---

## ⚙️ Settings

### GET `/settings/`
Get all settings. **Admin only.**

### PUT `/settings/{key}`
Update setting. **Admin only.**

---

## 🔔 Health

### GET `/`
Root health check.

**Response:**
```json
{
  "status": "healthy",
  "message": "Clinic Manager API",
  "version": "2.1.0"
}
```

### GET `/health`
Detailed health check.

---

## 🔑 Authentication Header

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

## 📝 HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Server Error |

## 🔒 Roles & Permissions

| Role | Access Level |
|------|-------------|
| Admin | Full access |
| Doctor | Patients, Visits, EMR |
| Registrar | Patients, Appointments |
| Cashier | Payments only |
| Patient | Own appointments/results |

---

## 📖 Links

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`
