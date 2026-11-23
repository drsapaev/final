/**
 * Mappers: patient-access DTOs → domain types (Phase 0 PR-A1/A2).
 *
 * Per ADR-0018 (Runtime Validation Strategy) each mapper validates its DTO
 * with zod before transformation, so backend contract drift is caught at the
 * transport boundary instead of silently reaching components.
 *
 * Note: `/patient-access/request-otp`, `/verify-otp` and `/login` are typed
 * on the backend as `dict[str, Any]` (uniform anti-enum responses); the
 * schemas below mirror the service payload shapes and are intentionally
 * strict about the fields the UI consumes.
 */

import { z } from 'zod';

import type {
  PatientActivationConfirmRequestDto,
  PatientActivationOtpRequestDto,
  PatientLoginRequestDto,
  PatientOtpRequestDto,
  PatientOtpVerifyRequestDto,
} from '../../types/api';
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
  PatientLoginResult,
} from '../../types/domain/patientAccess';

// --- response schemas -------------------------------------------------------

const patientOtpSentSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  expires_in_minutes: z.number(),
  resend_after_seconds: z.number(),
});

const patientOtpGrantSchema = z.object({
  success: z.boolean(),
  verification_grant: z.string().min(1),
  expires_in: z.number(),
});

const patientSessionUserSchema = z.object({
  id: z.number(),
  username: z.string(),
  email: z.string().nullable(),
  full_name: z.string().nullable(),
  role: z.string(),
  is_active: z.boolean(),
  is_superuser: z.boolean(),
});

const patientSessionSchema = z
  .object({
    access_token: z.string().min(1),
    token_type: z.string(),
    user: patientSessionUserSchema,
    patient_id: z.number().optional(),
  })
  .passthrough();

const patientActivationOtpSentSchema = z
  .object({
    success: z.boolean(),
    phone_masked: z.string(),
    expires_in_minutes: z.number(),
    resend_after_seconds: z.number(),
  })
  .passthrough();

const patientActivationTokenSchema = z
  .object({
    activation_token: z.string().min(1),
    expires_in_hours: z.number(),
    phone_masked: z.string(),
  })
  .passthrough();

// --- response mappers -------------------------------------------------------

export function mapPatientOtpSent(dto: unknown): PatientOtpSentResult {
  return patientOtpSentSchema.parse(dto);
}

export function mapPatientOtpGrant(dto: unknown): PatientOtpGrantResult {
  return patientOtpGrantSchema.parse(dto);
}

export function mapPatientSession(dto: unknown): PatientSession {
  return patientSessionSchema.parse(dto);
}

/** Parse either a complete patient session or a token-free second-factor challenge. */
export function mapPatientLoginResult(dto: unknown): PatientLoginResult {
  const data = z.record(z.string(), z.unknown()).parse(dto);
  if (data.requires_2fa === true) {
    if (data.access_token != null || data.refresh_token != null) throw new Error('Invalid pending authentication');
    const pending = z.object({
      requires_2fa: z.literal(true),
      two_factor_method: z.literal('totp'),
      pending_2fa_token: z.string().min(1).max(4096),
      user: patientSessionUserSchema,
    }).parse(data);
    if (pending.user.role.toLowerCase() !== 'patient' || !pending.user.is_active || pending.user.is_superuser) {
      throw new Error('Invalid patient authentication');
    }
    return pending;
  }
  if (data.requires_2fa != null && data.requires_2fa !== false) throw new Error('Invalid authentication result');
  const session = mapPatientSession(data);
  if (!session.access_token.trim() || session.token_type.toLowerCase() !== 'bearer' ||
      session.user.role.toLowerCase() !== 'patient' || !session.user.is_active || session.user.is_superuser) {
    throw new Error('Invalid patient authentication');
  }
  return session;
}

export function mapPatientTwoFactorResult(dto: unknown): { success: false } | { success: true; access_token: string; token_type: string } {
  const data = z.record(z.string(), z.unknown()).parse(dto);
  if (data.success === false) return { success: false };
  if (data.refresh_token != null) throw new Error('Unexpected refresh token');
  const result = z.object({ success: z.literal(true), access_token: z.string().min(1), token_type: z.string() }).parse(data);
  if (!result.access_token.trim() || result.token_type.toLowerCase() !== 'bearer') throw new Error('Invalid patient session');
  return result;
}

export function mapPatientActivationOtpSent(dto: unknown): PatientActivationOtpSentResult {
  return patientActivationOtpSentSchema.parse(dto);
}

export function mapPatientActivationToken(dto: unknown): PatientActivationTokenResult {
  return patientActivationTokenSchema.parse(dto);
}

// --- request re-type helpers ------------------------------------------------
// The wire shapes of the requests equal the domain inputs field-for-field;
// these helpers keep the api module free of `*Dto` naming while retaining the
// transport aliases for documentation and future drift handling.

export function toPatientOtpRequestDto(input: PatientOtpInput): PatientOtpRequestDto {
  return { phone: input.phone, locale: input.locale ?? undefined };
}

export function toPatientOtpVerifyRequestDto(input: PatientOtpCodeInput): PatientOtpVerifyRequestDto {
  return { phone: input.phone, code: input.code };
}

export function toPatientLoginRequestDto(input: PatientGrantLoginInput): PatientLoginRequestDto {
  return { phone: input.phone, verification_grant: input.verification_grant };
}

export function toPatientActivationOtpRequestDto(
  input: PatientActivationOtpInput
): PatientActivationOtpRequestDto {
  return { activation_token: input.activation_token, locale: input.locale ?? undefined };
}

export function toPatientActivationConfirmRequestDto(
  input: PatientActivationConfirmInput
): PatientActivationConfirmRequestDto {
  return { activation_token: input.activation_token, code: input.code };
}
