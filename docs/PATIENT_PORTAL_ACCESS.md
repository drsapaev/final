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

`/patient/activate?token=...` prefills the token field from a deep link.
The token is never auto-submitted: stale or revoked tokens surface as a
uniform error only after an explicit submit.

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
