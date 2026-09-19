/**
 * Patient portal access API (Phase 0).
 *
 * PR-A1: phone OTP login for an already-activated patient
 *        (request-otp → verify-otp → login with verification_grant).
 * PR-A2: registrar-issued card activation
 *        (staff: issue activation-token; public: activate/request-otp →
 *        activate/confirm → canonical patient session).
 *
 * Architecture (per src/api/mappers/index.ts): this module accepts and
 * returns DOMAIN types (types/domain/patientAccess.ts); transport DTOs and
 * zod validation live in src/api/mappers/patientAccess.ts.
 *
 * Session note: both flows return a canonical `User(role="Patient")` JWT
 * (owner identity contract v3, correction #5) — the caller stores it via the
 * standard auth store (stores/auth setToken/setProfile), NOT via the legacy
 * `patient_jwt_token` webauthn keys.
 *
 * Contract SSOT: backend/app/api/v1/endpoints/patient_access.py +
 * backend/app/services/patient_otp_service.py.
 */
import { api } from './client';
import { API_ENDPOINTS } from './endpoints';
import {
  mapPatientActivationOtpSent,
  mapPatientActivationToken,
  mapPatientOtpGrant,
  mapPatientOtpSent,
  mapPatientSession,
  toPatientActivationConfirmRequestDto,
  toPatientActivationOtpRequestDto,
  toPatientLoginRequestDto,
  toPatientOtpRequestDto,
  toPatientOtpVerifyRequestDto,
} from './mappers';
import type {
  PatientActivationConfirmInput,
  PatientActivationOtpInput,
  PatientActivationOtpSentResult,
  PatientActivationTokenResult,
  PatientGrantLoginInput,
  PatientOtpCodeInput,
  PatientOtpInput,
  PatientOtpGrantResult,
  PatientOtpSentResult,
  PatientSession,
} from '../types/domain/patientAccess';

/** PR-A1 step 1: send login OTP to the patient phone. */
export async function requestPatientOtp(
  input: PatientOtpInput
): Promise<PatientOtpSentResult> {
  const response = await api.post(
    API_ENDPOINTS.PATIENT_ACCESS.REQUEST_OTP,
    toPatientOtpRequestDto(input)
  );
  return mapPatientOtpSent(response.data);
}

/** PR-A1 step 2: verify the OTP → short-lived one-time verification_grant. */
export async function verifyPatientOtp(
  input: PatientOtpCodeInput
): Promise<PatientOtpGrantResult> {
  const response = await api.post(
    API_ENDPOINTS.PATIENT_ACCESS.VERIFY_OTP,
    toPatientOtpVerifyRequestDto(input)
  );
  return mapPatientOtpGrant(response.data);
}

/** PR-A1 step 3: exchange phone + grant for the canonical patient session. */
export async function patientLogin(
  input: PatientGrantLoginInput
): Promise<PatientSession> {
  const response = await api.post(
    API_ENDPOINTS.PATIENT_ACCESS.LOGIN,
    toPatientLoginRequestDto(input)
  );
  return mapPatientSession(response.data);
}

/** PR-A2 public step 1: request the activation OTP (OTP goes ONLY to the card phone captured at issuance). */
export async function requestActivationOtp(
  input: PatientActivationOtpInput
): Promise<PatientActivationOtpSentResult> {
  const response = await api.post(
    API_ENDPOINTS.PATIENT_ACCESS.ACTIVATE_REQUEST_OTP,
    toPatientActivationOtpRequestDto(input)
  );
  return mapPatientActivationOtpSent(response.data);
}

/** PR-A2 public step 2: confirm → atomic linking + canonical patient session. */
export async function confirmActivation(
  input: PatientActivationConfirmInput
): Promise<PatientSession> {
  const response = await api.post(
    API_ENDPOINTS.PATIENT_ACCESS.ACTIVATE_CONFIRM,
    toPatientActivationConfirmRequestDto(input)
  );
  return mapPatientSession(response.data);
}

/** PR-A2 staff: issue an activation token for a patient card (Admin|Registrar). */
export async function issueActivationToken(
  patientId: string | number
): Promise<PatientActivationTokenResult> {
  const response = await api.post(
    API_ENDPOINTS.PATIENT_ACCESS.ISSUE_ACTIVATION_TOKEN(patientId)
  );
  return mapPatientActivationToken(response.data);
}
