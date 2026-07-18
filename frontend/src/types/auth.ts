// src/types/auth.ts
// Phase 0.5 → revised: Domain auth types (NOT generated DTOs).
//
// ARCHITECTURE (per code review 2026-07-17):
//   generated DTO (from OpenAPI) → mapper (validates invariants) → domain type (this file)
//
// Rule: Generated types in src/types/generated/ are read-only and reflect OpenAPI
// one-to-one. Domain invariants (e.g. AUTHENTICATION_LAWS_FOR_AI.md ЗАКОН 2:
// "no access_token before 2FA") are enforced by mappers in auth-mapper.ts and
// expressed as discriminated unions here.
//
// This file contains ONLY domain types. It does NOT import from generated/api.ts.
// The raw transport shape is re-exported from src/types/api.ts as `LoginResponseRaw`,
// `TwoFactorVerifyResponseRaw`, etc. for advanced consumers / tests.
//
// SSOT for invariants: docs/AUTHENTICATION_LAWS_FOR_AI.md
// SSOT for transport shapes: backend/openapi.json → src/types/generated/api.ts

// ============================================================================
// Login step 1 — POST /authentication/login
// ============================================================================
//
// Domain invariant (AUTHENTICATION_LAWS_FOR_AI.md ЗАКОН 2):
//   requires_2fa === true  ⇒  access_token MUST NOT be present
//   requires_2fa === false ⇒  pending_2fa_token MUST NOT be present
//
// The discriminated union below makes this invariant unrepresentable at the
// type level — there is no `LoginResult` value where both branches coexist.
// The mapper (auth-mapper.ts) enforces it at runtime and throws if the
// backend violates the law.

/** Login succeeded, but 2FA verification required before access_token is issued. */
export interface LoginRequires2FA {
  requires_2fa: true;
  pending_2fa_token: string;
  two_factor_method?: string | null;
  must_change_password?: boolean;
}

/** Login succeeded, no 2FA required — tokens issued immediately. */
export interface LoginSucceeded {
  requires_2fa: false;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: unknown; // Domain User type — import from '@/types/api' at call sites to avoid cycle.
  must_change_password?: boolean;
}

/**
 * Discriminated union — use `requires_2fa` as the discriminant.
 * TS narrows automatically when you check `if (result.requires_2fa) { ... }`.
 *
 * ⚠️ This is the DOMAIN type, not the raw transport shape.
 * Use `parseLoginResponse(dto)` from auth-mapper.ts to convert.
 */
export type LoginResult = LoginRequires2FA | LoginSucceeded;

// ============================================================================
// 2FA verification — POST /2fa/verify
// ============================================================================

/** 2FA verify succeeded — tokens issued. */
export interface TwoFactorVerifySuccess {
  success: true;
  message: string;
  session_token?: string;
  device_trusted?: boolean;
  backup_codes_remaining?: number;
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
}

/** 2FA verify failed — no tokens. */
export interface TwoFactorVerifyFailure {
  success: false;
  message: string;
  session_token?: string;
  device_trusted?: boolean;
  backup_codes_remaining?: number;
}

/**
 * Discriminated union — use `success` as the discriminant.
 * Mapper: `parseTwoFactorVerifyResponse(dto)` from auth-mapper.ts.
 */
export type TwoFactorVerifyResult = TwoFactorVerifySuccess | TwoFactorVerifyFailure;

// ============================================================================
// 2FA verify request body — POST /2fa/verify
// ============================================================================

export interface TwoFactorVerifyRequest {
  totp_code?: string;
  backup_code?: string;
  recovery_token?: string;
  device_fingerprint?: string;
  remember_device?: boolean;
  pending_2fa_token: string;
}

// ============================================================================
// Token refresh — POST /authentication/refresh
// ============================================================================

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ============================================================================
// Type guards (operate on DOMAIN types, not raw DTOs)
// ============================================================================

export function isLoginRequires2FA(result: LoginResult): result is LoginRequires2FA {
  return result.requires_2fa === true;
}

export function isLoginSucceeded(result: LoginResult): result is LoginSucceeded {
  return result.requires_2fa === false;
}

export function isTwoFactorVerifySuccess(
  result: TwoFactorVerifyResult,
): result is TwoFactorVerifySuccess {
  return result.success === true;
}

// ============================================================================
// Backwards-compatibility aliases
//
// Early Phase 1 code (api/client.ts) was written against a flat union type
// called `LoginResponse`. To avoid churn while we propagate the DTO→mapper
// pattern, we keep `LoginResponse` as an alias of `LoginResult`.
// New code should use `LoginResult` directly.
// ============================================================================

/** @deprecated Use `LoginResult` instead. Alias kept for Phase 1 transition. */
export type LoginResponse = LoginResult;

/** @deprecated Use `TwoFactorVerifyResult` instead. Alias kept for transition. */
export type TwoFactorVerifyResponse = TwoFactorVerifyResult;

// Legacy branch-name aliases (used in early Phase 1 code; will be removed in Phase 9).
export type LoginStep1Response = LoginRequires2FA;
export type LoginStep1No2FAResponse = LoginSucceeded;
export type TwoFactorVerifySuccessResponse = TwoFactorVerifySuccess;
export type TwoFactorVerifyFailureResponse = TwoFactorVerifyFailure;

export function isLoginStep1Response(result: LoginResult): result is LoginRequires2FA {
  return result.requires_2fa === true;
}

export function isLoginStep1No2FAResponse(result: LoginResult): result is LoginSucceeded {
  return result.requires_2fa === false;
}
