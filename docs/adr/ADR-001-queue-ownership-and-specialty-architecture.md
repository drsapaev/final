# ADR-001: Queue Ownership & Specialty Architecture

**Status:** Accepted — amended 2026-09-07 (QD-2A: dual-owner axis for doctorless queues, see Addendum)
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

## Addendum (2026-09-07, QD-2A): Dual-Owner Axis for Doctorless Queues

**Status of this addendum:** Accepted (staged rollout in progress — stage A)
**Supersedes (partially):** the implicit assumption that EVERY `DailyQueue`
belongs to a doctor. The doctor-ownership decision itself is UNCHANGED.

### Context

Since ADR-001, doctorless queues (`lab`, `ecg`, the general fallback) were
served by **synthetic User+Doctor pairs** (`lab_resource` / `ecg_resource` /
`general_resource`, provisioned by migration 0055 and sandboxed by
QD-1.1/QD-1.2 role guards) — a workaround that kept `specialist_id` NOT NULL
at the cost of fake identities leaking into RBAC, user-management and
booking surfaces (the cleanup effort those guards required is exactly the
debt this design retires).

### Decision

`DailyQueue` gains a second nullable ownership axis, `queue_resource_id`
(FK → `queue_resources`), where `queue_resources` is a **reference registry,
not an account**: no User, no role, no login. The terminal state is an XOR —
**exactly one owner** per queue: a doctor (`specialist_id`, ADR-001 semantics
unchanged, including same-specialty collaboration) or a resource
(`queue_resource_id`).

The rollout is staged, one PR per stage:

| Stage | Scope |
|---|---|
| **A (this change)** | Schema EXPAND: `queue_resources` table + nullable `queue_resource_id` + `specialist_id` NULLABLE. No XOR, no uniqueness, no seeds, no runtime switch. Migration `0058`. |
| B | Seed `lab`/`ecg` registry rows + exact-tag-wins duplicate resolution (inventory-before-mutation, loud abort). |
| C | Runtime switch: resolvers, morning pre-create, queue API identity (`DailyQueue.id`), output contract (`owner_kind`), GQL nullable. |
| D | CONTRACT: XOR CHECK + partial active uniqueness (`UNIQUE(day, queue_resource_id) WHERE active AND queue_resource_id IS NOT NULL`). |
| E | Retire the synthetic User+Doctor pairs (paired deletion), remove the bridge vocabulary. |

**The `general` resource is deliberately conditional, not forgotten.** Stage B
seeds `lab` and `ecg` only — the `general` tag becomes a registry row ONLY if
the QD-2B inventory proves it is a real standalone routing tag rather than a
mixed bucket. Its destination is an explicit operator decision (registry row
in a stage-B follow-up, or retirement of general-queue routing with the load
moved to explicit tags) that must land BEFORE stage E can retire
`general_resource` — stage E is gated on zero live references for all three
synthetic pairs, so general queues can never be left without an owner.

### Stage B landing note (2026-09-07, QD-2B — migration 0059)

Stage B landed the seeds from LIVE catalog proof (a tag seeds only when its
active services are homogeneous `requires_doctor = false`) and the
deterministic backfill. Three clarifications the landing made explicit:

- "duplicate resolution" in the table above is **loud abort, never dedup**:
  more than one ACTIVE queue for one `(day, resource tag)` stops the
  migration with a full per-row inventory, and the repair (deactivate or
  reassign) is an explicit operator decision. No QueueEntry merge ever
  happens in stage B — the partial active uniqueness arrives in stage D.
- The backfill is the **dual-ownership bridge**: `specialist_id` keeps
  pointing at the old synthetic Doctor while `queue_resource_id` is set. The
  destination follows `queue_tag` (exact-tag-wins), never the owner username
  — a `general_resource`-owned `lab` queue bridges onto the lab resource.
- Seed configuration **transfers the live synthetic Doctor numbering** (the
  values the queue machinery reads today, not the 0055 constants) with
  display names from the canonical 0055 vocabulary; `default_cabinet` stays
  NULL because no canonical cabinet source exists.

### Stage C landing note (2026-09-07, QD-2C — runtime switch)

Stage C switched the runtime onto the resource axis. The switch is
**conditional on live registry data** — a tag routes onto the resource axis
ONLY while an ACTIVE `queue_resources` row exists for the exact tag
(`laboratory` never resolves the `lab` resource). With no registry row
(empty test DBs, the CI `alembic upgrade head` chain, `general`,
`stomatology`, doctor specialties), every path keeps its legacy behavior
byte-identical — the legacy synthetic fallbacks stay functional until
stage E retires them. Four clarifications the landing made explicit:

- **Tag-first unification** — `get_or_create_daily_queue` (queue_svc, the
  crud wrapper and the visit-confirmation repository) resolves a registry
  tag by `(day, queue_tag)` regardless of owner: the dual-ownership bridge
  from 0059, a resource-owned row and a pre-switch synthetic-owned row are
  ONE routing surface. A specialist-keyed caller (QR token, GQL joinQueue,
  a visit with a doctor) is unified onto that queue instead of forking a
  parallel doctor-owned queue — the pre-QD-2 fork hazard is closed for
  registry tags; doctor tags keep the per-doctor PR-26 contract.
- **New queues are resource-owned** — `specialist_id` NULL +
  `queue_resource_id` + caps from the registry row; the synthetic Doctor is
  no longer resolved by morning pre-create, morning assignment, batch
  create, visit confirmation or the registrar wizard (the QD-2E direction:
  a registry-only catalog no longer needs `general_resource` at all).
- **Output contract** — `DailyQueueOut` grew `owner_kind` ("doctor" |
  "resource"), `owner_display_name` and a `queue_resource` object; the GQL
  `DailyQueueType.specialist` is now nullable with `queue_resource_id` +
  `owner_kind`. The axis is derived from `queue_resource_id` — the bridge
  classifies as resource (the axis that owns routing going forward).
- **Numbering** — `calculate_next_number` floors a resource queue at
  `QueueResource.start_number_online` (the LIVE values 0059 transferred;
  identical to the synthetic's until E), and the GQL advisory lock for a
  registry tag keys on `(tag, day)` instead of `(doctor, day, tag)`.

### Guidance for readers of this ADR

Anything that routes, authorizes, or reports on queues must treat ownership
as **doctor XOR resource** from stage C onward. "Every `DailyQueue` belongs to
a doctor" in the sections above now reads "every **doctor** queue belongs to
a doctor; **doctorless** queues belong to a `queue_resources` row." During
stages A–B both axes coexist at the schema level and no production path
writes a resource-owned row; stage D enforces the XOR at the DB level.

### Migration Path

- `0058_queue_resource_expand` (stage A): additive DDL; strict downgrade
  (re-tightening `specialist_id` NOT NULL fails loudly if resource-owned
  rows exist — history preservation first).
- Existing doctor-owned rows: byte-compatible, untouched at every stage.
- Synthetic identities: removed only in stage E, after zero references.

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
