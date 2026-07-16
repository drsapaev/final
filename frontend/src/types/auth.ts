// src/types/auth.ts
// Phase 0.5 — Auth flow types.
// Plan: JS-to-TS-Migration-Plan v3, section 0.5.4
//
// SSOT: docs/AUTHENTICATION_LAWS_FOR_AI.md (ЗАКОН 2: Блокирующий 2FA флоу)
//   + backend/openapi.json (raw shapes: LoginResponse, TwoFactorVerifyResponse, etc.)
//
// ⚠️ ЗАПРЕЩЕНО: возвращать access_token до завершения 2FA.
// Дискриминированное объединение ниже enforcement-ит этот инвариант на уровне типов:
// при `requires_2fa: true` тип НЕ содержит `access_token`.
//
// Raw OpenAPI-схема делает все поля nullable (плоский superset) — это особенность
// Pydantic. Семантический контракт описан в AUTHENTICATION_LAWS_FOR_AI.md и отражён
// здесь как discriminated union.

import type { User } from './api';

// ============================================================================
// Login step 1 — POST /authentication/login
// ============================================================================

/** Login succeeded, but 2FA verification required before access_token is issued. */
export interface LoginStep1Response {
  pending_2fa_token: string;
  requires_2fa: true;
  two_factor_method?: string | null;
  must_change_password?: boolean;
  // ⚠️ access_token / refresh_token MUST NOT be present in this branch.
}

/** Login succeeded, no 2FA required — tokens issued immediately. */
export interface LoginStep1No2FAResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  requires_2fa: false;
  must_change_password?: boolean;
  // ⚠️ pending_2fa_token MUST NOT be present in this branch.
}

/**
 * Discriminated union — use `requires_2fa` as the discriminant.
 * TS will narrow the type when you check `if (response.requires_2fa) { ... }`.
 */
export type LoginResponse = LoginStep1Response | LoginStep1No2FAResponse;

// ============================================================================
// 2FA verification — POST /2fa/verify
// ============================================================================

export interface TwoFactorVerifyRequest {
  totp_code?: string;
  backup_code?: string;
  recovery_token?: string;
  device_fingerprint?: string;
  remember_device?: boolean;
  pending_2fa_token: string;
}

/** 2FA verify succeeded — tokens issued. */
export interface TwoFactorVerifySuccessResponse {
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
export interface TwoFactorVerifyFailureResponse {
  success: false;
  message: string;
  session_token?: string;
  device_trusted?: boolean;
  backup_codes_remaining?: number;
  // ⚠️ access_token / refresh_token MUST NOT be present in this branch.
}

/**
 * Discriminated union — use `success` as the discriminant.
 */
export type TwoFactorVerifyResponse = TwoFactorVerifySuccessResponse | TwoFactorVerifyFailureResponse;

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
// Type guards
// ============================================================================

export function isLoginStep1Response(response: LoginResponse): response is LoginStep1Response {
  return response.requires_2fa === true;
}

export function isLoginStep1No2FAResponse(response: LoginResponse): response is LoginStep1No2FAResponse {
  return response.requires_2fa === false;
}

export function isTwoFactorVerifySuccess(
  response: TwoFactorVerifyResponse,
): response is TwoFactorVerifySuccessResponse {
  return response.success === true;
}
