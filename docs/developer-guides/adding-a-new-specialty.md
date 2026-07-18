# Developer Guide: Adding a New Medical Specialty

**Last updated:** 2026-07-12
**Applies to:** MediClinic Pro backend + frontend
**Prerequisite:** Admin access to the system

---

## Overview

The system supports adding new medical specialties (e.g., neurology,
endocrinology, ultrasound, pediatrics) **without writing any code**.
This guide walks through the complete process and explains what happens
at each step.

For architectural details, see [ADR-001: Queue Ownership & Specialty Architecture](../adr/ADR-001-queue-ownership-and-specialty-architecture.md).

---

## Quick Start (5 Steps)

### Step 1: Create a Department

**Admin Panel → Clinic Management → Отделения → "Добавить отделение"**

| Field | Value | Notes |
|---|---|---|
| Название (рус) | Неврология | Display name in Russian |
| Название (узб) | Nevrologiya | Display name in Uzbek |
| Ключ | `neurology` | **Must be lowercase latin, digits, underscore only.** This is the canonical specialty key. |
| Порядок | 50 | Display order in tabs |
| Иконка | `Brain` | Lucide icon name |
| Цвет | `#8B5CF6` | Hex color for tab badge |

**What happens automatically:**
- `Department` row created in database
- `DepartmentQueueSettings` created (queue prefix, max daily queue)
- `DepartmentRegistrationSettings` created
- `ServiceCategory` created for this department
- Default `Service` created ("Консультация (Неврология)")
- `DepartmentService` link created
- **`QueueProfile` auto-created** with:
  - `key = "neurology"`
  - `title_ru = "Неврология"`
  - `queue_tags = ["neurology"]`
  - `show_on_qr_page = true`
  - `is_active = true`

### Step 2: Create a Doctor User

**Admin Panel → User Management → "Добавить пользователя"**

| Field | Value |
|---|---|
| Username | `neuro_ivanov` |
| Email | `ivanov@clinic.com` |
| Full Name | `Иванов И.И.` |
| Role | `Doctor` (or `cardio`/`derma`/`dentist` for specialty panels) |
| Password | (set a secure password) |
| Is Active | ✅ |

**What happens automatically:**
- `User` row created
- `UserProfile` created (with full_name, phone, etc.)
- `UserPreferences` created
- `UserNotificationSettings` created
- **`Doctor` row auto-created** with `specialty="general"` (if role is `Doctor`)
  - If role is `cardio` → `specialty="cardiology"`
  - If role is `derma` → `specialty="dermatology"`
  - If role is `dentist` → `specialty="dentistry"`

### Step 3: Link Doctor to the New Specialty

**Admin Panel → Врачи → Edit the doctor you just created**

| Field | Value |
|---|---|
| Пользователь | (already selected) |
| Специальность | `neurology` (select from dropdown — populated from Departments) |
| Кабинет | `201` |
| Цена по умолчанию | `80000` |
| Активен | ✅ |

**What happens:**
- `Doctor.specialty` updated from `"general"` to `"neurology"`
- Doctor is now visible in:
  - Registrar wizard doctor selector (when filtering by neurology department)
  - QR page (if doctor is active and QueueProfile has `show_on_qr_page=true`)

### Step 4: Add Services for the Specialty

**Admin Panel → Услуги → Справочник услуг → "Добавить услугу"**

| Field | Value | Notes |
|---|---|---|
| Name | ЭЭГ головного мозга | Service name |
| Code | `N01` | **First letter determines category.** For new departments, use any letter not already taken (K=cardio, D=derma, S=dental, L=lab, C/P/O=procedures). `N` is a good choice for neurology. |
| Category | (select or create) | Service category |
| Price | `120000` | Price in UZS |
| Department | `neurology` | Links service to the department |
| Queue Tag | `neurology` | Tags the service for queue routing |
| Requires Doctor | ✅ | If this service requires a doctor consultation |
| Is Consultation | ✅ | If this is a consultation (affects repeat-discount logic) |

### Step 5: Verify End-to-End

1. **Doctor logs in:**
   - `GET /auth/me` returns `{specialty: "neurology"}`
   - Routes to `DoctorPanel` (generic panel — works for all specialties)
   - Sees their queue (tagged `neurology`)

2. **Registrar creates a visit:**
   - Opens wizard on "Неврология" tab
   - Service selector shows neurology services (filtered by `department_key`)
   - Doctor selector shows only neurology doctors (filtered by service specialty)
   - Patient is assigned to the specific doctor's queue

3. **Patient scans QR:**
   - Sees "Невропатолог" with correct icon and color (from QueueProfile)
   - Selects specific doctor (e.g., "Иванов И.И. · каб. 201")
   - Joins that doctor's queue with their own number

4. **Doctor calls patient:**
   - Any neurology doctor can call patients from any neurology queue
   - Queue numbers are per-doctor (independent)

---

## Architecture Overview

### Data Model

```
User (id, username, role, ...)
  └── Doctor (id, user_id, specialty, cabinet, ...)
        └── DailyQueue (id, specialist_id=Doctor.id, day, queue_tag, active)
              └── OnlineQueueEntry (id, daily_queue_id, patient_name, status, ...)

Department (id, key, name_ru, ...)
  └── QueueProfile (id, key, title_ru, queue_tags[], show_on_qr_page, ...)
  └── Service (id, department_key, name, price, queue_tag, ...)
  └── DepartmentService (department_id, service_id)
```

### Key Principles

1. **Queue ownership = Doctor** (`DailyQueue.specialist_id`)
2. **Specialty identity = `Doctor.specialty`** (not `User.role`)
3. **Specialty display = `QueueProfile`** (name, icon, color, visibility)
4. **Department key = Specialty key** (they must match: `department.key` = `doctor.specialty` = `queue_profile.key`)

### What's Dynamic (No Hardcoding)

| What | Source | How |
|---|---|---|
| Queue creation | `Doctor.id` | `get_or_create_daily_queue(specialist_id=doctor.id)` |
| Queue access | `Doctor.specialty` | Same-specialty doctors can collaborate |
| Home route | `profile.specialty` | `getRoleHomeRoute()` checks specialty |
| Doctor panel queue | `profile.specialty` | `useDoctorQueue(specialty)` |
| QR page display | `QueueProfile` | Name, icon, color from profile |
| QR visibility | `QueueProfile.show_on_qr_page` | Admin toggles in UI |
| Wizard service filter | `QueueProfile.queue_tags` | Dynamic filter in `getWizardDepartmentFilterKeys` |
| Wizard doctor filter | `Service.department_key` | Filter by matching `Doctor.specialty` |
| DoctorModal specialty | `/admin/departments` | Dropdown populated from API |
| Specialty mapping | `QueueProfile` records | Built dynamically in `_get_clinic_wide_selectable_specialists` |

### What's Still Hardcoded (Intentionally)

| What | Why | Impact |
|---|---|---|
| `DOCTOR_QUEUE_SPECIALTY_VARIANTS` | Legacy alias mapping (cardio↔cardiology) | None — fallback `[specialty]` works for unknown |
| `DOCTOR_QUEUE_ALLOWED_TAGS` | Legacy tag mapping | None — fallback `[specialty]` works for unknown |
| `QR_SPECIALTY_ALIASES` | Normalizes cardio→cardiology | None — unknown specialties pass through as-is |
| `SPECIALTY_START_NUMBERS` | Per-specialty queue start number | All queues start at #1 by default — acceptable |
| Specialty panel components | Cardio/Derma/Dental have unique clinical features | New specialties use generic `DoctorPanel` |

---

## Adding a Dedicated Panel (Optional)

If a new specialty needs specialty-specific clinical features (like ECG for
cardiology or dental chart for dentistry), you can create a dedicated panel.

### When to create a dedicated panel

- The specialty has unique clinical workflows (e.g., EEG for neurology)
- The specialty needs custom EMR templates
- The generic `DoctorPanel` is insufficient for the clinical workflow

### How to create a dedicated panel

1. **Create the component:**
   ```
   frontend/src/pages/NeurologistPanelUnified.jsx
   ```
   Start by copying `DoctorPanel.jsx` and adding specialty-specific tabs.

2. **Register the route** in `frontend/src/routing/routeRegistry.js`:
   ```javascript
   {
     id: 'doctor-neurology',
     path: '/doctor/neurology',
     group: 'clinical',
     surface: 'screen',
     lifecycle: stable,
     shell: 'app-shell',
     auth: 'role-scoped',
     roles: ['Admin', 'Doctor', 'neurology'],
     homeForRoles: ['neurology'],
     component: 'NeurologistPanelUnified',
     layout: layout({ fullscreen: true, sidebarPreset: 'neurology', pageTitle: 'Neurology Panel' }),
   },
   ```

3. **Add the role** to `UserCreateRequest.role` pattern in `schemas/user_management.py`:
   ```python
   role: str = Field(..., pattern="^(Admin|Registrar|Doctor|...|neurology)$")
   ```

4. **Add to `ROLE_HOME_PRIORITY`** in `routeRegistry.js`:
   ```javascript
   export const ROLE_HOME_PRIORITY = [
     'admin', 'cardio', 'derma', 'dentist', 'neurology',
     'registrar', 'lab', 'cashier', 'doctor', 'patient',
   ];
   ```

5. **Add specialty route mapping** in `routeSelectors.js` `getRoleHomeRoute`:
   ```javascript
   const specialtyRouteMap = {
     'cardiology': '/doctor/cardiology',
     // ...
     'neurology': '/doctor/neurology',
   };
   ```

6. **Add EMR templates** in `frontend/src/utils/emrSpecialty.js` (optional).

### When NOT to create a dedicated panel

- The specialty only needs queue management + basic visit workflow
- The generic `DoctorPanel` is sufficient
- You want to ship quickly and iterate later

The generic `DoctorPanel` handles:
- Queue display (filtered by `Doctor.specialty`)
- Patient calling (call next, start visit, complete, no-show)
- Visit management (EMR, prescriptions, lab orders)
- AI assistant (if enabled)

---

## Troubleshooting

### Doctor sees empty queue

**Cause:** `Doctor.specialty` doesn't match any `DailyQueue.queue_tag`.

**Fix:**
1. Check `GET /auth/me` → verify `specialty` field is returned
2. Check `Doctor.specialty` in database matches the `QueueProfile.key`
3. Ensure a `DailyQueue` exists for this doctor (create a test visit via wizard)

### Doctor routed to wrong panel

**Cause:** `getRoleHomeRoute` doesn't recognize the specialty.

**Fix:**
1. Known specialties (cardiology, dermatology, dentistry) → dedicated panel
2. Unknown specialties → `DoctorPanel` (generic) — this is correct behavior
3. If you need a dedicated panel, follow the "Adding a Dedicated Panel" guide above

### Patient doesn't see the specialty on QR page

**Cause:** `QueueProfile.show_on_qr_page` is `false` or no active doctor exists.

**Fix:**
1. Admin → Вкладки регистратуры → edit the profile → check "Показывать на QR-странице"
2. Ensure at least one active `Doctor` with matching `specialty` exists
3. Check `QueueProfile.is_active = true`

### New service not visible in wizard

**Cause:** Service `department_key` doesn't match the active tab's `queue_tags`.

**Fix:**
1. Check `Service.department_key` matches `Department.key`
2. Check `QueueProfile.queue_tags` includes the department key
3. Ensure `Service.active = true`

---

## References

- [ADR-001: Queue Ownership & Specialty Architecture](../adr/ADR-001-queue-ownership-and-specialty-architecture.md)
- [Multi-Doctor & Specialty Architecture Audit](../../../download/MULTI_DOCTOR_SPECIALTY_AUDIT.md)
- [Admin Flows Audit](../../../download/ADMIN_FLOWS_AUDIT.md)
- [Wizard & QR UX Audit](../../../download/WIZARD_QR_UX_AUDIT.md)
