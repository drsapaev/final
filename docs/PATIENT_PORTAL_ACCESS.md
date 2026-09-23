# Patient Portal Access — OTP Login & Card Activation (Phase 0)

Phase 0 patient-access track documentation. Covers the public, passwordless
patient flows delivered in PR-A1 (backend OTP foundation, #3313), PR-A2
(registrar-issued activation + atomic linking, #3320) and PR-B (frontend,
this document ships with the PR-B delivery).

## Overview

Patients authenticate to the portal (`/patient`) without passwords:

1. **Activation (one-time, per card)** — a clinic Admin issues an activation
   token from the patients table (`/admin/patients` → key icon). The patient
   enters the token on `/patient/activate`, receives an OTP on the phone
   recorded on the card, confirms, and lands in the portal with a session.
   The backend atomically links `User` + `UserProfile` + `Patient.user_id`.
2. **Login (every subsequent visit)** — the activated patient enters their
   phone number on `/patient/login`, receives an OTP on the card phone, and
   confirms the 6-digit code.

Both flows produce the same canonical `User(role="Patient")` JWT session
(identity contract v3, owner correction #5): the frontend stores it through
the standard auth store (`tokenManager` + `stores/auth`), so the existing
role-scoped route boundary (`RouteAccessBoundary`, `homeForRoles: ['patient']`)
admits the patient to `/patient`. There is no separate patient session path.

## Routes (frontend, PR-B)

| Route | Access | Purpose |
|-------|--------|---------|
| `/patient/login` | public | Phone + OTP login for activated patients (PR-A1) |
| `/patient/activate` | public | Activation-token + OTP card activation (PR-A2) |
| `/patient` | role-scoped (`Patient` + support roles) | Patient portal home |

Both public pages follow the landing shell (`hideHeader`/`hideSidebar`),
carry no nav entry, and are registered in `src/routing/routeRegistry.ts`
(ids `patient-login`, `patient-activate`; owner `iam.patient-access`).
The route smoke suite (`frontend/e2e/frontend-10-route-smoke.spec.ts`)
covers both routes as public surfaces.

`/patient/activate#token=...` prefills the token field from a deep link.
The token is never auto-submitted: stale or revoked tokens surface as a
uniform error only after an explicit submit.

**Deep-link form (Phase 0 follow-up):** the canonical handout link carries
the token in the URL **fragment** (`#token=...`). The browser never
transmits the fragment to the server, so Vercel rewrites, access logs and
any infrastructure in front of the SPA never observe the 72-hour
credential on the first HTTP navigation (the legacy `?token=...` query
form was visible to that infrastructure before the SPA booted and could
only be stripped after JS load). The legacy query form keeps working for
links already handed out within the TTL; both forms are copied into state
and immediately stripped from the URL/history after prefill. BOTH handout
forms are additionally extracted and stripped during app bootstrap BEFORE
telemetry (Sentry) initialization (`utils/patientActivateDeepLink.ts`,
called from `main.tsx` before `initSentry()`): the query component of a
legacy link survives in `window.location` until the page effect, and the
Sentry scrubber redacts token-keyed object fields but not URL-valued
telemetry fields — so the bootstrap strip covers the fragment AND the
legacy query (unrelated query params and an unrelated hash are preserved;
the canonical fragment wins when a URL carries both). Defense-in-depth:
`services/sentry.ts` additionally redacts credential query/fragment params
(token + `*_token`, api keys, secret, password, sig/signature,
authorization) inside URL-valued telemetry strings (`request.url`,
breadcrumb from/to, Referer) and in transactions via
`beforeSendTransaction` (pageload traces bypass `beforeSend`), so a
pageload trace or startup error must never observe the credential at all.

## Staff issuance (PR-A2)

- Surface: `/admin/patients` row action (key icon) → two-stage dialog
  (`PatientActivationTokenDialog`).
- Stage 1 is an explicit confirmation because **reissuing revokes the
  previous token** (per-patient revocation index on the backend).
- Stage 2 shows the token **once** (hash-only storage server-side), the
  masked card phone, and the TTL (72h). One click copies the token.
- RBAC: the endpoint allows `Admin|Registrar`; the current web patients
  table is Admin-only, so the dialog ships on the Admin surface. Registrar
  issuance is available via the API and will follow with a registrar
  patients surface.

## Backend contract (SSOT: `backend/app/api/v1/endpoints/patient_access.py`)

### PR-A1 login

| Step | Endpoint | Request | Response |
|------|----------|---------|----------|
| 1 | `POST /api/v1/patient-access/request-otp` | `{phone, locale?}` (`locale ∈ {ru, uz}`) | `{success, message, expires_in_minutes: 5, resend_after_seconds: 60}` |
| 2 | `POST /api/v1/patient-access/verify-otp` | `{phone, code}` (6 digits) | `{success, verification_grant, expires_in}` |
| 3 | `POST /api/v1/patient-access/login` | `{phone, verification_grant}` | `{access_token, token_type: "bearer", user{...role: "Patient"}}` |

### PR-A2 activation

| Step | Endpoint | Request | Response |
|------|----------|---------|----------|
| 0 (staff) | `POST /api/v1/patients/{patient_id}/activation-token` | `{}` (no body) | 201 `{activation_token, expires_in_hours, phone_masked}` |
| 1 | `POST /api/v1/patient-access/activate/request-otp` | `{activation_token, locale?}` | `{success, phone_masked, expires_in_minutes, resend_after_seconds}` |
| 2 | `POST /api/v1/patient-access/activate/confirm` | `{activation_token, code}` | `{access_token, token_type, user{...}, patient_id}` |

### Error model (applies to both flows)

- Phone format: `+998XXXXXXXXX` (validated client-side via
  `normalizeUzbekPhoneForApi`/`isValidUzbekPhone` before submit).
- `400` — uniform generic invalid token/OTP (anti-enum: no PHI in details).
- `401` — generic login failure (fail-closed resolver: 0 or >1 active
  verified Patient-users on the phone → single generic 401).
- `404` — unknown/deleted patient (staff issuance only).
- `409` — card already linked (or commit race backstop).
- `429` — rate-limited: IP 5/min OTP, 10/min confirm+issue; phone
  cooldown/cap per namespace (login and activation are isolated).
- `503` — SMS/Redis unavailable (fail-closed).

## Frontend implementation map (PR-B)

| Concern | File |
|---------|------|
| API module (domain in/out) | `frontend/src/api/patientAccess.ts` |
| DTO→domain zod mappers | `frontend/src/api/mappers/patientAccess.ts` |
| Domain types | `frontend/src/types/domain/patientAccess.ts` |
| Transport DTO aliases | `frontend/src/types/api.ts` |
| Endpoint constants | `frontend/src/api/endpoints.ts` (`PATIENT_ACCESS`) |
| Login page | `frontend/src/pages/auth/PatientLoginPage.tsx` |
| Activation page | `frontend/src/pages/auth/PatientActivatePage.tsx` |
| Issuance dialog | `frontend/src/components/admin/PatientActivationTokenDialog.tsx` |
| Route registry entries | `frontend/src/routing/routeRegistry.ts` |
| i18n namespace | `patientPortal` (all 5 locales: ru, en, kk, uz-Latn, uz-Cyrl) |

Notes:

- `/patient-access/*` endpoints are listed in `AUTH_BOOTSTRAP_SUFFIXES`
  (`frontend/src/api/client.ts`): their uniform 400/401/429 must surface as
  form errors and must never trigger the reactive token-refresh path (a
  patient session carries no refresh token; a 401 here means "wrong code /
  not activated", not "expired").
- Session storage uses the standard `tokenManager` keys
  (`auth_token`/`user`), not the legacy webauthn `patient_jwt_token` keys.
- Access-only session lifecycle (Phase 0 follow-up): a patient session has
  no refresh token, so a 401 on a business endpoint after the 30-minute
  JWT expiry terminates the session through `stores/auth.clearToken()`
  (registered into `api/client.ts` via `setSessionInvalidationListener`),
  clearing `auth_token`/`auth_profile` + tokenManager + PHI caches and
  notifying subscribers — `RouteAccessBoundary` redirects to the login
  page immediately. The clear keeps the same race guard as the reactive
  refresh path: it fires only when the failed token is still the live
  access token, so a mid-flight re-login is never wiped.
- Issuance 409 semantics (Phase 0 follow-up): the backend returns two
  distinct safe 409 details on `POST /patients/{id}/activation-token` —
  `ERR_PATIENT_ALREADY_LINKED` (this card already linked) and
  `ERR_ISSUANCE_PHONE_BOUND` (card not linked, but the phone is already
  bound to another portal card — family/shared phone). The issuance dialog
  maps them to separate localized messages (`pi_error_already_linked` vs
  `pi_error_phone_bound`); the phone-bound detail string is mirrored as a
  pinned literal in the dialog and pinned by backend unit tests.

## Related

- Backend phase record: PR #3313 (PR-A1), #3320 (PR-A2).
- Route contract tests: `frontend/src/routing/__tests__/routeContract.test.ts`.
- Unit tests: `frontend/src/pages/auth/__tests__/`,
  `frontend/src/api/__tests__/patientAccess.test.ts`,
  `frontend/src/components/admin/__tests__/PatientActivationTokenDialog.test.tsx`.

## Phase 1 (PR-C1): JWT patient portal self-service

Phase 0 OTP patients land on `/patient` with a canonical `User(role="Patient")`
JWT. PR-C1 adds the web counterpart of the Mini App self-service surface so
the portal no longer depends on Telegram identity:

| Capability | Endpoint (JWT, `Patient` role, own scope) | Mini App counterpart (unchanged) |
|------------|-------------------------------------------|----------------------------------|
| Cabinet summary | `GET /api/v1/patients/cabinet/summary` | `POST /api/v1/telegram/mini-app/cabinet/summary` |
| Booking preview | `POST /api/v1/patients/booking/preview` | `POST /api/v1/telegram/mini-app/appointments/preview` |
| Booking create | `POST /api/v1/patients/booking` (201) | `POST /api/v1/telegram/mini-app/appointments` |
| Forms (read-only) | `GET /api/v1/patients/forms` | `POST /api/v1/telegram/mini-app/forms/preview` |

Contract notes:

- Single source of truth: all four endpoints reuse the Mini App service layer
  (`build_telegram_mini_app_appointment_booking_preview`,
  `build_telegram_mini_app_patient_forms_preview`, the cabinet summary payload
  assembly). Identity differs only at the scope boundary — the JWT endpoints
  build a `TelegramMiniAppSessionScope` from `current_user.patient.id` with
  `telegram_user_id`/`telegram_chat_id` set to `None` (the dataclass fields are
  optional since PR-C1; Telegram-sourced scopes keep real ids).
- Booking creation mirrors the Mini App contract exactly: per-doctor
  `FOR UPDATE` slot reservation taken BEFORE eligibility, same 409
  `appointment_time_slot_occupied`, same doctor lifecycle eligibility.
- Error mapping: request-shaped booking problems are `400`
  (`appointment_date_in_past`, `doctor_id_invalid`, ...), identity/scope
  problems are `403`; a `User` without a linked patient card gets `404
  patient_profile_required`; unauthenticated is `401`.
- Deliberately out of scope: web form SUBMISSIONS. The
  `telegram_patient_form_submissions.telegram_chat_id` column is `NOT NULL`,
  so a web submission path requires its own schema decision first. The web
  forms endpoint is read-only (`POST /patients/forms` is 405).
- Router mount order matters: `patient_portal` is included BEFORE
  `patients.router` so static `/patients/forms` and `/patients/booking` win
  over `GET /patients/{patient_id}`.
- Audit: every endpoint writes a `patient_access_audit` row (actor = JWT user,
  scope = patient portal scope).

Round-2 hardening (review of PR #3340, applies to all four endpoints):

- Principal validity: the shared portal dependency composes
  `get_current_active_user` + `require_roles("Patient")`. An
  admin-deactivated `User` gets `403` on every portal endpoint even with an
  unexpired JWT (`require_roles` alone never checks `is_active`).
- Soft-deleted card: `Patient.is_deleted = true` yields `403
  patient_link_invalid` — the same SSOT check the Mini App scope resolver
  applies (soft deletion only flips the flag; `User.patient` keeps
  resolving, so the check must be explicit).
- Department resolution: booking `department` is the canonical
  `Department.key` (`cardio`, `echokg`, `derma`, `dental`, `lab`,
  `procedures`). Unknown keys → `400 department_unknown`; deactivated
  departments → `400 department_inactive`. The created `Appointment` gets
  the resolved `department_id` (the routing context the schedule and
  department-schedule reads join on); the raw string is display metadata.
- Booking idempotency: `POST /patients/booking` REQUIRES an
  `Idempotency-Key` header (missing header → `422`). PR-C2 must generate
  one key per booking attempt and REUSE it on retry: same key + same
  payload replays the committed `201` (no duplicate appointment), same key
  + changed payload is a `409`. Date-only/department-only requests have no
  doctor slot lock, so the mandated key is the only duplicate protection
  for those shapes.
- Typed contract: all four endpoints publish explicit Pydantic response
  DTOs (`PatientPortalCabinetSummaryResponse`,
  `PatientPortalBookingPreviewResponse`, `PatientPortalBookingCreatedResponse`,
  `PatientPortalFormsResponse`) and document their 4xx surface
  (`PatientPortalErrorResponse`, `detail` = `{reason, message?}` from
  portal guards or a plain string from the auth/RBAC layer). The generated
  TypeScript (`src/types/generated/api.ts`) is part of the PR-C2 contract
  and is freshness-gated in CI.

Round-3 hardening (review of PR #3340 @ `42465f8`, applies to the portal +
the idempotency middleware):

- Patient-aware replay policy: the idempotency namespace now binds the
  CURRENT active Patient card (`patient:{id}`) on top of the canonical
  user id. A snapshot committed under card A can never be replayed after
  the account is re-linked to card B (different namespace → fresh
  execution). A MISSING or soft-deleted card bypasses the idempotency
  machinery entirely: the retry reaches the endpoint's own guards and is
  answered `404 patient_profile_required` / `403 patient_link_invalid`
  exactly like a first request — a committed booking can no longer be
  replayed to a revoked card within the 24h key TTL.
- Operation-scoped keys: the namespace also binds `METHOD + normalized
  path`, so one `Idempotency-Key` can never alias two operations that
  share a request DTO (`POST /patients/booking/preview` vs
  `POST /patients/booking`): a replay only ever satisfies the same
  operation it was produced by. The Redis claim keys and execution-intent
  markers inherit the same scoping. Existing stored snapshots expire
  naturally (24h TTL); a deploy re-executes each key at most once.
- Cabinet policy SSOT parity: `PatientPortalCabinetPolicy` carries the
  full Mini App policy payload (`plain_telegram_chat_allowed`,
  `medical_details_in_chat`, `pdf_included`) — response filtering no
  longer drops `medical_details_in_chat`.
- Typed 404 surface: `404 patient_profile_required` is now DECLARED for
  preview, booking and forms (only cabinet declared it before); booking
  additionally documents the doctor-eligibility 404. The generated
  TypeScript is regenerated from the spec (CI freshness gate).
- Internal creation schema: `department_id` was removed from the shared
  `AppointmentCreate` and lives only on the portal-internal
  `PatientPortalAppointmentCreate`. `POST /patients/booking` persists the
  server-resolved `departments.id`; the legacy `POST /appointments/`
  contract is back to its pre-#3340 shape (no client-owned routing FK —
  the read model `Appointment` still exposes `department_id`).
- Denied audit rows: portal refusals write `outcome="denied"`
  `patient_access_audit` rows with `extra_data.reason`
  (`patient_link_invalid` 403, `department_unknown`/`department_inactive`
  400, `doctor_not_eligible` 404, `appointment_time_slot_occupied` 409)
  and `extra_data.surface = "jwt_portal"`. The soft-deleted-card 403
  carries the revoked card id as the audit subject. A refusal with no
  subject at all (no linked card) writes no row — the same SSOT boundary
  the Mini App applies to auth failures without a patient context.

Round-4 hardening (review of PR #3340 @ `e8fec8f`, applies to the portal +
the idempotency middleware + canonical Appointment reads):

- Canonical Appointment reads survive a persisted department: the ORM
  `Appointment.department` is the Department RELATIONSHIP while the read
  DTO declared `department: str | None` under the same attribute name —
  the first row with a non-NULL `department_id` (which the portal booking
  now guarantees) made `Appointment.model_validate()` coerce a Department
  OBJECT into a string and 500'd `GET /appointments/` (one poisoned row
  killed the whole list) and `GET /appointments/{id}`. The read model now
  maps the relationship explicitly (legacy `department` field → canonical
  key, `str | null` contract preserved) and publishes typed
  `department_key` / `department_name` fields backed by ORM accessors.
- Stable key→card binding (idempotency): the round-3 namespace scoping
  alone made a same-key retry look FRESH after a card re-link (the
  namespace moved WITH the current card), so the lost-response retry
  re-executed the booking for the NEW patient — two appointments for two
  patients from one logical submit. The key is now bound to the card it
  FIRST ran under, in the ORIGIN namespace (canonical user + operation,
  no patient scope) — the identity that survives a re-link. A retry whose
  current card differs from the bound one is refused non-executing with
  `409 idempotency_scope_mismatch`; the re-linked card books with a NEW
  key. Durable binding in Redis (`:pscope` key, 24h TTL) + per-process
  mirror for the degraded path (same contract as execution intents).
- Rollout-compatible namespace transition: pre-#3340 outcomes and
  execution-intent markers live under the user-only namespace for up to
  24h and were INVISIBLE to the operation-scoped namespace — a same-key
  retry after deploy would re-execute a write whose outcome is already
  committed or unknown. Before claiming, the middleware now reconciles
  the LEGACY namespace (one raw read pass, `probe_legacy_artifacts`):
  a stored legacy RESPONSE replays under the full replay contract
  (payload hash, principal authorization, endpoint role policy) and
  MIGRATES to the current namespace (bounded TTL extension); a legacy
  INTENT without an outcome refuses conservatively
  (`409 idempotency_uncertain_outcome`); a legacy in-flight claim refuses
  as `409 idempotency_in_flight` until the pre-deploy worker completes.
  Scoped to principals WITHOUT a patient scope: legacy snapshots cannot
  be attributed to the CURRENT card, and every patient-facing keyed
  endpoint is new in #3340 (no legacy keys exist for patients) — staff
  endpoints (the legacy keyed traffic) reconcile fully. Redis is NOT
  cleared: that would destroy the very outcomes and unknown-outcome
  guards that protect against duplicates.
- Deactivated-account audit trail: the composed dependency refused a
  deactivated account BEFORE the endpoint body ran, so the linked card's
  per-patient trail lost the attempt. The portal dependency is now a
  factory (`_active_portal_user_audited(resource_type, action)`): resolve
  the actor, write the `outcome="denied"` row (reason
  `user_deactivated`, subject = linked card when one exists), THEN raise
  the 403. Same defect class `require_active_roles` (PR #3333) fixed for
  the control plane. The factory product publishes `required_roles` for
  the idempotency middleware (Codex R6 #3092 convention) per endpoint.
- Department normalization: the SSOT builder strips the draft department
  while the portal resolver queried the RAW request string —
  `" cardio "` passed the builder, then missed the exact `Department.key`
  match and 400'd `department_unknown` for a department the preview had
  already accepted. The resolver now strips internally and both booking
  endpoints resolve the SSOT-NORMALIZED `preview.draft.department`.
- Cabinet department label: `Department` has no `name` column (only
  `key` / `name_ru` / `name_uz`), so the shared cabinet builder returned
  `department: null` for every booked row. It now displays `name_ru`
  (canonical `key` fallback) — Mini App and JWT portal both benefit.

Round-7 hardening (review of PR #3340 @ `9bb31dc`, applies to the idempotency
middleware + the published OpenAPI surface):

- Redis outage AFTER the DB commit can no longer orphan an old-version
  worker: the migration fence now writes a LEGACY execution intent
  (owner-bound to the fence token) BEFORE the handler runs, and
  `store_response()` reports whether Redis CONFIRMED the write instead of
  returning `None` for both success and transport failure. A confirmed
  outcome dual-writes both namespaces and only then deletes both intent
  markers; a known non-2xx deletes them and releases the fence; a Redis
  death on the post-commit store keeps the new-namespace intent, the
  legacy intent and the fence up until the lease lapses — old workers
  reconcile (`409 idempotency_uncertain_outcome`) instead of finding an
  empty legacy namespace and re-executing the committed write. REQUIRED
  coordination that loses Redis BETWEEN the two intent marks fails closed
  (`503`) before executing.
- The local scope-binding mirror and the local response snapshot are ONE
  atomic entry: `(origin user + operation + key) → patient_scope →
  payload_hash → response snapshot`, shared LRU fate. The round-6 layout
  (two independent caches) let an LRU eviction of the binding leave a
  live response invisible to the relink-refusal, so a re-linked card
  could re-bind the key and execute a second write. Patient-scope
  operations now replay from the atomic entry; the durable Redis layer
  (unchanged layout) covers a fully evicted mirror. A KNOWN non-2xx
  DROPS its pre-handler binding (local + value-guarded Redis twin), so a
  flood of invalid keyed requests cannot evict durable successful
  bindings — the round-6 eviction vector.
- The bounded mirror is now O(1) per operation at capacity: overflow is
  an immediate LRU popitem (the round-6 full TTL sweep per `set()` after
  the bound was reached — O(N) per request, ~O(N²) for a flood — is
  gone). TTL hygiene moved to a lazy expiry heap (incremental, bounded
  budget per op) with amortized compaction, so expired entries are
  reclaimed without ever scanning the whole store.
- The keyed surface of `POST /patients/booking/preview` is PUBLISHED:
  optional `Idempotency-Key` header (1..128 chars, same bound as the
  create endpoint) plus typed `409` (idempotency_payload_mismatch /
  idempotency_in_flight / idempotency_uncertain_outcome /
  idempotency_scope_mismatch) and `503 idempotency_unavailable`. The
  middleware already processed keyed previews (the operation-scoping
  contract exercises it), so the generated TypeScript now describes the
  real outcomes.

Round-11 parity (follow-up after PR #3340 merged, applies to the Telegram
Mini App booking endpoints):

- Canonical doctor-department routing on the Mini App surface: the shared
  booking helper (`_build_mini_app_appointment_booking_preview_from_request`,
  used by BOTH `POST /telegram/mini-app/appointments/preview` and
  `POST /telegram/mini-app/appointments`) now resolves the SAME routing
  context the portal got in rounds 9-10. The routing resolvers moved to
  the shared SSOT service `app/services/appointment_booking_routing.py`
  (`resolve_booking_department`, `resolve_doctor_routing_department`,
  `attach_department_id`); the portal keeps behavior-identical aliases.
  Contract (identical 400 reasons on both surfaces, BEFORE any mutation):
  `department_unknown` / `department_inactive` (submitted key),
  `doctor_department_missing` (doctor without a canonical department — an
  explicit refusal, never a NULL routing context),
  `doctor_department_mismatch` (submitted department is not the doctor's
  own), `department_inactive` on the CANONICAL path (round-10 owner P1
  parity). Create re-resolves on the LOCKED doctor row AFTER eligibility
  and BEFORE the slot check, and persists `department_id` through the
  internal `PatientPortalAppointmentCreate` schema — a Mini App
  doctor-booking no longer stores `department_id = NULL` (the
  department-pop follow-up flagged in round 2).
- Preview/create routing agreement: the preview response echoes the
  resolved `appointment.department_id` (additive field,
  `response_model=dict[str, Any]` — no OpenAPI/api.ts churn), and the
  create response's `preview` payload carries the same value, so a
  patient always sees the routing context the row actually got.
- Clinic-local calendar on the Mini App surface: the booking past-day
  check receives `today=clinic_today(db)` (Asia/Tashkent queue-settings
  SSOT) — the round-9 owner P2 fix now covers BOTH patient-facing
  surfaces. On a UTC host between 00:00 and 04:59 Tashkent time the
  previous clinic day is refused (`400 appointment_date_in_past`) instead
  of being accepted by the host's `date.today()`.
- Denial audit parity: routing refusals on the Mini App surface write
  `outcome="denied"` `patient_access_audit` rows with the failing reason
  (same SSOT pattern as the portal's round-3 denied rows); success rows
  carry the resolved `department_id`.
