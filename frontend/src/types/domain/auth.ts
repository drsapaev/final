/**
 * Domain types for authentication, authorization, and user management.
 *
 * Used by:
 *   - stores/auth.ts (the actual auth store — token + profile snapshot)
 *   - types/auth-store.ts (store API surface)
 *   - contexts/ChatContext.tsx, contexts/ThemeContext.tsx
 *   - routing/routeGuards.tsx, components/layout/Nav.tsx
import type { UserId } from './branded';
 *   - LoginForm, UserManagement, RoleGate, security components
 *
 * Consolidation note (Wave 3, Domain Adoption 100%):
 * Previously AuthState was declared locally in three places (stores/auth.ts,
 * types/auth-store.ts, contexts/ChatContext.tsx) with slightly different
 * shapes. All three have been merged into the canonical shape below.
 * The pre-existing "AuthState { user, token, refreshToken, status, ... }"
 * variant that was never actually used by any consumer has been renamed
 * to AuthSessionState — it represents a richer React-context-style state
 * and may be adopted in Wave 4 when the auth UI is refactored.
 */

export type UserRole = 'admin' | 'doctor' | 'nurse' | 'registrar' | 'cashier' | 'lab' | 'patient';
export type AuthStatus = 'authenticated' | 'unauthenticated' | 'loading' | 'error';

// === Store-level auth snapshot (CANONICAL) ==================================
// This is the actual shape returned by stores/auth.ts getState().
// All consumers (routeGuards, Nav, ChatContext, etc.) must use this type.

export interface UserProfile {
  id?: number | null;
  name?: string;
  full_name?: string;
  username?: string;
  email?: string;
  role?: string;
  role_name?: string;
  specialty?: string;
  admin?: unknown;
  clinic_id?: unknown;
  doctor_id?: unknown;
  is_admin?: unknown;
  is_superuser?: unknown;
  specialist_id?: unknown;
  roles?: unknown;
}

export interface AuthState {
  token: string | null;
  profile: UserProfile | null;
}

// === Richer auth context state (FUTURE) =====================================
// A more complete auth state shape for richer UI contexts (status, errors,
// refresh tokens). Currently unused — reserved for Wave 4 auth refactor.
// Kept here so domain consumers can opt into the richer shape without
// redefining it locally.

export interface AuthSessionState {
  user: AuthUser | null;
  token: string | null;
  refreshToken: string | null;
  status: AuthStatus;
  error: string | null;
  isAuthenticated: boolean;
}

export interface AuthUser {
  id: string | number;
  email?: string;
  full_name?: string;
  name?: string;
  role?: UserRole;
  roles?: string[];
  phone?: string;
  avatar?: string | null;
  is_active?: boolean;
}

export type AuthAction =
  | { type: 'LOGIN_START' }
  | { type: 'LOGIN_SUCCESS'; payload: { user: AuthUser; token: string; refreshToken?: string } }
  | { type: 'LOGIN_ERROR'; payload: { error: string } }
  | { type: 'LOGOUT' }
  | { type: 'REFRESH_TOKEN'; payload: { token: string } }
  | { type: 'UPDATE_USER'; payload: { user: Partial<AuthUser> } }
  | { type: 'CLEAR_ERROR' };

export interface Permission {
  id?: string | number;
  code?: string;
  name?: string;
  description?: string;
}

export interface Role {
  id?: string | number;
  name?: string;
  code?: string;
  permissions?: Permission[];
}

/**
 * Database record for a role, as returned by GET /roles.
 * Stricter shape than the abstract `Role` above — every field is required
 * because the backend role-management endpoint always returns the full row.
 *
 * Was previously declared locally in src/hooks/useRoles.ts; consolidated
 * here in Wave 3.
 */
export interface RoleRecord {
  id: number;
  name: string;
  display_name: string;
  description: string;
  level: number;
  is_active: boolean;
  is_system: boolean;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

// ============================================================================
// Login flow — discriminated unions with invariant enforcement
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
//
// Consolidated here in Wave G6 from src/types/auth.ts (deleted).

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
 * This is the DOMAIN type, not the raw transport shape.
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

/** 2FA verify request body — POST /2fa/verify */
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
// called `LoginResponse`. Kept as alias of `LoginResult` for transition.
// New code should use `LoginResult` directly.
// ============================================================================

/** @deprecated Use `LoginResult` instead. Alias kept for transition. */
export type LoginResponse = LoginResult;

/** @deprecated Use `TwoFactorVerifyResult` instead. Alias kept for transition. */
export type TwoFactorVerifyResponse = TwoFactorVerifyResult;

// Legacy branch-name aliases (used in early Phase 1 code).
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

export interface TokenPayload {
  sub?: string | number;
  exp?: number;
  iat?: number;
  role?: string;
  roles?: string[];
}

export interface SessionInfo {
  session_id?: string;
  user_id?: string | number;
  ip_address?: string;
  user_agent?: string;
  created_at?: string;
  expires_at?: string;
  is_active?: boolean;
}
