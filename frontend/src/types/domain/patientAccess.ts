/**
 * Domain types for patient portal access (Phase 0: PR-A1 login + PR-A2 activation).
 *
 * Used by PatientLoginPage, PatientActivatePage, PatientActivationTokenDialog,
 * and api/patientAccess.ts.
 *
 * Architecture (per mappers/index.ts, Wave 4/5 Domain Adoption):
 * components consume ONLY these domain types; the transport DTOs
 * (types/api.ts `*Dto`) are mapped inside src/api/mappers/patientAccess.ts.
 *
 * Session contract (owner identity contract v3, correction #5): both the
 * login and the activation flows return a canonical `User(role="Patient")`
 * session — the caller stores it via stores/auth (setToken/setProfile), so
 * the standard role-scoped route boundary admits the patient to /patient.
 */

/** Step-1 input: request a login OTP (PR-A1). */
export interface PatientOtpInput {
  phone: string;
  locale?: 'ru' | 'uz' | null;
}

/** Uniform step-1 result (backend is intentionally anti-enum). */
export interface PatientOtpSentResult {
  success: boolean;
  message: string;
  expires_in_minutes: number;
  resend_after_seconds: number;
}

/** Step-2 input: verify the SMS code (PR-A1). */
export interface PatientOtpCodeInput {
  phone: string;
  code: string;
}

/** Step-2 result: short-lived one-time verification grant. */
export interface PatientOtpGrantResult {
  success: boolean;
  verification_grant: string;
  expires_in: number;
}

/** Step-3 input: exchange phone + grant for the canonical session (PR-A1). */
export interface PatientGrantLoginInput {
  phone: string;
  verification_grant: string;
}

/** Canonical session user mirrored from the backend service payload. */
export interface PatientSessionUser {
  id: number;
  username: string;
  email: string | null;
  full_name: string | null;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
  [key: string]: unknown;
}

/** Canonical patient session (PR-A1 login / PR-A2 confirm). */
export interface PatientSession {
  access_token: string;
  token_type: string;
  user: PatientSessionUser;
  /** PR-A2 confirm only. */
  patient_id?: number;
  [key: string]: unknown;
}

/** Activation step-1 input: the staff-issued activation token (PR-A2). */
export interface PatientActivationOtpInput {
  activation_token: string;
  locale?: 'ru' | 'uz' | null;
}

/** Activation step-1 result: OTP went to the masked card phone. */
export interface PatientActivationOtpSentResult {
  success: boolean;
  phone_masked: string;
  expires_in_minutes: number;
  resend_after_seconds: number;
  [key: string]: unknown;
}

/** Activation step-2 input: token + SMS code (PR-A2). */
export interface PatientActivationConfirmInput {
  activation_token: string;
  code: string;
}

/** Staff issuance result: one-time display of the activation token (PR-A2). */
export interface PatientActivationTokenResult {
  activation_token: string;
  expires_in_hours: number;
  phone_masked: string;
  [key: string]: unknown;
}
