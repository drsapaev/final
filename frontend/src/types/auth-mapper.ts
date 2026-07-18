// src/types/auth-mapper.ts
// Phase 0.5 → revised: Mappers that convert raw generated DTOs into domain
// types, validating business invariants at the boundary.
//
// ARCHITECTURE (per code review 2026-07-17):
//
//     HTTP JSON
//         ↓
//     Generated DTO (src/types/generated/api.ts — read-only, never edited)
//         ↓
//     Mapper (THIS FILE — validates invariants, throws on violation)
//         ↓
//     Domain Type (src/types/auth.ts — discriminated unions, type-safe)
//         ↓
//     UI / application code
//
// Why this layer exists:
//   - Generated types reflect the OpenAPI transport contract one-to-one.
//     They say "which fields MAY appear in JSON" but cannot express
//     inter-field invariants like "if requires_2fa is true, access_token
//     MUST be absent".
//   - The mapper enforces those invariants at runtime. If the backend ever
//     accidentally sends `{ requires_2fa: true, access_token: "..." }`, the
//     mapper throws — surfacing the backend bug loudly instead of letting
//     it silently corrupt auth state.
//
// SSOT for invariants: docs/AUTHENTICATION_LAWS_FOR_AI.md (ЗАКОН 2: blocking 2FA flow)

import type {
  LoginResponseRaw,
  TwoFactorVerifyResponseRaw,
} from './api';
import type {
  LoginResult,
  LoginRequires2FA,
  LoginSucceeded,
  TwoFactorVerifyFailure,
  TwoFactorVerifyResult,
  TwoFactorVerifySuccess,
} from './auth';

// ============================================================================
// Errors
// ============================================================================

/**
 * Thrown when the backend returns a structurally valid DTO that violates a
 * business invariant. Surfaces backend bugs loudly instead of silently
 * corrupting auth state.
 */
export class AuthInvariantViolationError extends Error {
  readonly invariant: string;
  readonly dto: unknown;

  constructor(invariant: string, message: string, dto: unknown) {
    super(`[AuthInvariantViolation] ${invariant}: ${message}`);
    this.name = 'AuthInvariantViolationError';
    this.invariant = invariant;
    this.dto = dto;
  }
}

// ============================================================================
// Login response mapper
// ============================================================================

/**
 * Convert a raw LoginResponse DTO (flat nullable superset from OpenAPI) into
 * the domain LoginResult discriminated union.
 *
 * Invariants enforced (AUTHENTICATION_LAWS_FOR_AI.md ЗАКОН 2):
 *   - requires_2fa === true  ⇒  access_token MUST NOT be present
 *   - requires_2fa === false ⇒  pending_2fa_token MUST NOT be present
 *                                access_token + refresh_token MUST be present
 *
 * @throws AuthInvariantViolationError if the backend violates ЗАКОН 2.
 */
export function parseLoginResponse(dto: LoginResponseRaw): LoginResult {
  if (dto.requires_2fa === true) {
    // Branch 1: 2FA required. pending_2fa_token must be present,
    // access_token must be absent.
    if (dto.access_token != null) {
      throw new AuthInvariantViolationError(
        'AUTH_LAW_2_BLOCKING_2FA',
        'Backend returned requires_2fa=true together with access_token. ' +
          'Access tokens MUST NOT be issued before 2FA verification (AUTHENTICATION_LAWS_FOR_AI.md ЗАКОН 2).',
        dto,
      );
    }
    if (!dto.pending_2fa_token) {
      throw new AuthInvariantViolationError(
        'AUTH_LAW_2_BLOCKING_2FA',
        'Backend returned requires_2fa=true without pending_2fa_token. ' +
          'Cannot proceed with 2FA flow without a pending token.',
        dto,
      );
    }
    const result: LoginRequires2FA = {
      requires_2fa: true,
      pending_2fa_token: dto.pending_2fa_token,
    };
    if (dto.two_factor_method != null) result.two_factor_method = dto.two_factor_method;
    if (dto.must_change_password !== undefined) result.must_change_password = dto.must_change_password;
    return result;
  }

  if (dto.requires_2fa === false) {
    // Branch 2: no 2FA. Tokens must be present, pending_2fa_token must be absent.
    if (dto.pending_2fa_token != null) {
      throw new AuthInvariantViolationError(
        'AUTH_LAW_2_BLOCKING_2FA',
        'Backend returned requires_2fa=false together with pending_2fa_token. ' +
          'pending_2fa_token MUST NOT be issued when 2FA is not required.',
        dto,
      );
    }
    if (!dto.access_token) {
      throw new AuthInvariantViolationError(
        'AUTH_LAW_2_BLOCKING_2FA',
        'Backend returned requires_2fa=false without access_token. ' +
          'Login must issue access_token when 2FA is not required.',
        dto,
      );
    }
    if (!dto.refresh_token) {
      throw new AuthInvariantViolationError(
        'AUTH_LAW_2_BLOCKING_2FA',
        'Backend returned requires_2fa=false without refresh_token. ' +
          'Login must issue refresh_token when 2FA is not required.',
        dto,
      );
    }
    const result: LoginSucceeded = {
      requires_2fa: false,
      access_token: dto.access_token,
      refresh_token: dto.refresh_token,
      token_type: dto.token_type ?? 'bearer',
      expires_in: dto.expires_in,
      user: dto.user,
    };
    if (dto.must_change_password !== undefined) result.must_change_password = dto.must_change_password;
    return result;
  }

  // requires_2fa is undefined or wrong type — treat as invariant violation.
  throw new AuthInvariantViolationError(
    'AUTH_LAW_2_BLOCKING_2FA',
    `Backend returned LoginResponse with requires_2fa=${String(dto.requires_2fa)} ` +
      '(expected true or false).',
    dto,
  );
}

// ============================================================================
// 2FA verify response mapper
// ============================================================================

/**
 * Convert a raw TwoFactorVerifyResponse DTO into the domain
 * TwoFactorVerifyResult discriminated union.
 *
 * Invariants enforced:
 *   - success === true  ⇒  access_token + refresh_token MUST be present
 *   - success === false ⇒  access_token MUST NOT be present
 *
 * @throws AuthInvariantViolationError if the backend violates these invariants.
 */
export function parseTwoFactorVerifyResponse(dto: TwoFactorVerifyResponseRaw): TwoFactorVerifyResult {
  if (dto.success === true) {
    if (!dto.access_token) {
      throw new AuthInvariantViolationError(
        'TWO_FACTOR_VERIFY_SUCCESS_REQUIRES_TOKENS',
        'Backend returned 2FA verify success=true without access_token. ' +
          'Successful 2FA verification MUST issue access_token.',
        dto,
      );
    }
    if (!dto.refresh_token) {
      throw new AuthInvariantViolationError(
        'TWO_FACTOR_VERIFY_SUCCESS_REQUIRES_TOKENS',
        'Backend returned 2FA verify success=true without refresh_token. ' +
          'Successful 2FA verification MUST issue refresh_token.',
        dto,
      );
    }
    const result: TwoFactorVerifySuccess = {
      success: true,
      message: dto.message,
      access_token: dto.access_token,
      refresh_token: dto.refresh_token,
    };
    if (dto.session_token != null) result.session_token = dto.session_token;
    if (dto.device_trusted !== undefined) result.device_trusted = dto.device_trusted;
    if (dto.backup_codes_remaining != null) result.backup_codes_remaining = dto.backup_codes_remaining;
    if (dto.token_type != null) result.token_type = dto.token_type;
    if (dto.expires_in != null) result.expires_in = dto.expires_in;
    return result;
  }

  if (dto.success === false) {
    if (dto.access_token != null) {
      throw new AuthInvariantViolationError(
        'TWO_FACTOR_VERIFY_FAILURE_MUST_NOT_HAVE_TOKENS',
        'Backend returned 2FA verify success=false together with access_token. ' +
          'Failed 2FA verification MUST NOT issue tokens.',
        dto,
      );
    }
    const result: TwoFactorVerifyFailure = {
      success: false,
      message: dto.message,
    };
    if (dto.session_token != null) result.session_token = dto.session_token;
    if (dto.device_trusted !== undefined) result.device_trusted = dto.device_trusted;
    if (dto.backup_codes_remaining != null) result.backup_codes_remaining = dto.backup_codes_remaining;
    return result;
  }

  throw new AuthInvariantViolationError(
    'TWO_FACTOR_VERIFY_SUCCESS_FLAG_INVALID',
    `Backend returned TwoFactorVerifyResponse with success=${String(dto.success)} ` +
      '(expected true or false).',
    dto,
  );
}

// ============================================================================
// Safe wrappers (return Either-style: { ok: true, value } | { ok: false, error })
// ============================================================================

export type ParseOk<T> = { ok: true; value: T };
export type ParseErr = { ok: false; error: AuthInvariantViolationError };
export type ParseResult<T> = ParseOk<T> | ParseErr;

/**
 * Same as parseLoginResponse, but returns an Either instead of throwing.
 * Useful in React components where throwing inside render is undesirable.
 */
export function tryParseLoginResponse(dto: LoginResponseRaw): ParseResult<LoginResult> {
  try {
    return { ok: true, value: parseLoginResponse(dto) };
  } catch (e) {
    if (e instanceof AuthInvariantViolationError) return { ok: false, error: e };
    throw e; // Unexpected — rethrow.
  }
}

/**
 * Same as parseTwoFactorVerifyResponse, but returns an Either.
 */
export function tryParseTwoFactorVerifyResponse(
  dto: TwoFactorVerifyResponseRaw,
): ParseResult<TwoFactorVerifyResult> {
  try {
    return { ok: true, value: parseTwoFactorVerifyResponse(dto) };
  } catch (e) {
    if (e instanceof AuthInvariantViolationError) return { ok: false, error: e };
    throw e;
  }
}
