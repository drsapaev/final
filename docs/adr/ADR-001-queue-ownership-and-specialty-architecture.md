# ADR-001: Queue Ownership & Specialty Architecture

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Backend team, Frontend team
**Supersedes:** SSOT queue_tag-based shared queue (removed in PR-26)

---

## Context

The clinic management system supports multiple doctors of the same specialty
(e.g., 3 cardiologists, 6 dentists) and must be extensible to new specialties
(neurology, endocrinology, ultrasound, etc.) without code changes.

Prior to PR-26..PR-28, the system had a **critical architectural contradiction**:

- **Data model** (`DailyQueue.specialist_id` FK → `doctors.id`): queue belongs to **doctor**
- **Service layer** (`get_or_create_daily_queue`): queue belongs to **specialty** (`queue_tag`)

This caused:
- All doctors of the same specialty silently shared ONE queue
- 403 Forbidden when a non-owner doctor tried to call patients
- Meaningless doctor selection in the wizard
- Queue numbers shared across doctors

Additionally, specialty routing was role-based (`User.role = "cardio"`) not
specialty-based (`Doctor.specialty = "cardiology"`), and multiple hardcoded
specialty lists prevented adding new specialties without code changes.

---

## Decision

### 1. Queue Owner: **Doctor** (not specialty)

**DailyQueue belongs to a specific doctor**, identified by `specialist_id`
(FK → `doctors.id`).

- `get_or_create_daily_queue(day, specialist_id, queue_tag)` searches by
  `(day, specialist_id, active=True)` FIRST. `queue_tag` is stored for
  routing/display but does NOT override per-doctor ownership.
- Each doctor has their own independent queue number sequence.
- Any doctor of the **same specialty** can call/start/cancel patients
  from any same-specialty queue (not just the owner).
- Admin can always operate any queue.

**Rationale:** Patients choose a specific doctor (e.g., "I want Dr. Ivanov"),
not just a specialty. Each doctor needs their own queue to manage their
own patient flow. The `queue_tag` is retained for display board routing
and department-level filtering, but ownership is per-doctor.

### 2. Specialty Source of Truth: **Doctor.specialty** (not User.role)

**`Doctor.specialty`** is the canonical field for specialty identity.

- `GET /auth/me` returns `specialty`, `doctor_id`, `cabinet` for doctor users.
- Frontend `getRoleHomeRoute()` checks `profile.specialty` to route to the
  correct panel (cardiology → `/doctor/cardiology`, etc.).
- `DoctorPanel` reads `specialty` from auth profile and passes it to
  `useDoctorQueue(specialty)` — no hardcoding.
- `User.role` is still used for access control (`cardio`, `derma`, `dentist`
  roles grant access to the corresponding specialty panel), but routing
  is driven by `Doctor.specialty`.

**Known specialties** (`cardiology`, `dermatology`, `dentistry`) have
dedicated panel components (`CardiologistPanelUnified`, etc.).

**Unknown specialties** (e.g., `neurology`, `endocrinology`) fall through
to `DoctorPanel` (generic), which reads `specialty` from the profile and
loads the correct queue.

### 3. Adding a New Specialty: **No code changes required**

The system is designed so that a new specialty (e.g., neurology) can be
added entirely through the admin UI:

1. Admin creates a **Department** (`key="neurology"`)
   → Auto-creates `QueueProfile` (with `show_on_qr_page=True`) and
     default Service (PR-16)
2. Admin creates a **User** with `role="Doctor"`
   → Auto-creates `Doctor` row with `specialty="general"` (PR-17)
3. Admin edits the **Doctor** → sets `specialty="neurology"` via
   dropdown populated from `/admin/departments` (PR-19)
4. Doctor logs in → `/auth/me` returns `{specialty: "neurology"}`
   → Routes to `DoctorPanel` (generic) → sees neurology-tagged queue
5. Patient scans QR → sees "Невропатолог" (name from `QueueProfile.title_ru`)
   → Selects specific doctor → joins that doctor's queue

**What works automatically:**
- Queue creation (per-doctor, via `get_or_create_daily_queue`)
- QR page display (specialty name/icon/color from `QueueProfile`)
- Wizard service filter (dynamic via `queueProfiles`, PR-25)
- Doctor filter in wizard (by `service.department_key`, PR-23)
- Queue visibility (specialty fallback in `_resolve_queue_allowed_tags`)
- Same-specialty collaboration (any neurologist can call patients)

**What requires a dedicated panel component (optional, not blocking):**
- Specialty-specific clinical features (ECG for cardiology, dental chart
  for dentistry, etc.)
- Until a dedicated panel is built, the generic `DoctorPanel` handles
  queue management, patient calling, and basic visit workflow.

### 4. Components That MUST Be Dynamic

The following components must NOT contain hardcoded specialty lists.
They must derive specialty information from `QueueProfile` or `Doctor.specialty`:

| Component | Source of Truth | Was Hardcoded? | Fixed in |
|---|---|---|---|
| `get_or_create_daily_queue` | `specialist_id` (per-doctor) | Yes (queue_tag dedupe) | PR-26 |
| `call_patient` / `start_visit` / `cancel` | `Doctor.specialty` comparison | Yes (user_id match) | PR-26 |
| `GET /auth/me` | `Doctor.specialty` lookup | Yes (no specialty field) | PR-27 |
| `getRoleHomeRoute` | `profile.specialty` | Yes (homeForUsernames) | PR-27/28 |
| `DoctorPanel` queue load | `profile.specialty` via `getProfile()` | Yes ('general') | PR-27 |
| `_get_clinic_wide_selectable_specialists` | `QueueProfile` records | Yes (hardcoded mapping) | PR-28 |
| `QR_HIDDEN_PROFILE_KEYS` | `QueueProfile.show_on_qr_page` flag | Yes ({"ecg","general"}) | PR-28 |
| `_resolve_queue_allowed_tags` | Fallback `[specialty]` for unknown | Had fallback (OK) | PR-28 (docstring) |
| `_resolve_queue_specialty_variants` | Fallback `[specialty]` for unknown | Had fallback (OK) | PR-28 (docstring) |
| `getWizardDepartmentFilterKeys` | `QueueProfile.queue_tags` (dynamic) | Yes (hardcoded map) | PR-25 |
| `DoctorModal` specialty dropdown | `/admin/departments` | Yes (free text) | PR-19 |
| `UserCreateRequest.role` pattern | Includes `cardio/derma/dentist` | Yes (excluded) | PR-26 |

---

## Consequences

### Positive

- **Multi-doctor clinics work correctly:** 3 cardiologists each have their
  own queue with independent numbers.
- **New specialties work without code changes:** neurology, endocrinology,
  ultrasound, etc. can be added via admin UI.
- **Clear ownership model:** `DailyQueue.specialist_id` is the single source
  of truth for queue ownership.
- **Same-specialty collaboration:** any cardiologist can call patients from
  any cardiology queue (not just their own).
- **Extensible routing:** unknown specialties fall through to generic
  `DoctorPanel`; dedicated panels can be added incrementally.

### Negative

- **More DailyQueue rows:** each doctor gets their own queue (was: one per
  specialty). For a clinic with 10 cardiologists, that's 10 queues per day
  instead of 1. This is acceptable — each queue is lightweight (a single
  `DailyQueue` row + its `OnlineQueueEntry` children).
- **Display board needs awareness:** if the display board shows one queue
  per specialty, it must now aggregate multiple doctors' queues. This is
  a future enhancement (P3 backlog).
- **EMR skeleton:** new specialties get an empty EMR template (no
  specialty-specific fields like ECG for cardiology). This is a functional
  limitation, not an architectural defect — empty EMR is better than
  hardcoded fields that don't apply.

### Migration Path (for existing clinics)

- **Existing shared queues:** will continue to work — they have a valid
  `specialist_id` pointing to the first doctor. New queues created after
  PR-26 will be per-doctor.
- **No data migration needed:** the schema already has `specialist_id`
  on `DailyQueue`. The fix is in the service layer logic only.
- **Rollback:** reverting PR-26 restores shared-queue behavior (all
  doctors of same specialty share one queue). This is safe but loses
  per-doctor isolation.

---

## References

- PR-26: `get_or_create_daily_queue` per-doctor fix + same-specialty 403 removal
- PR-27: `/auth/me` returns specialty; `getRoleHomeRoute` uses specialty
- PR-28: Dynamic specialty mapping from QueueProfile; removed hardcoded lists
- PR-25: Dynamic wizard department filter from queue profiles
- PR-23: Doctor filter by service department in wizard cart
- PR-19: DoctorModal specialty dropdown from `/admin/departments`
- PR-16: Auto-create QueueProfile on Department create
- PR-17: Auto-create Doctor row on User create with role=Doctor
- Audit: `/home/z/my-project/download/MULTI_DOCTOR_SPECIALTY_AUDIT.md`
