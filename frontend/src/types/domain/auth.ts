/**
 * Domain types for authentication, authorization, and user management.
 *
 * Used by:
 *   - stores/auth.ts (the actual auth store — token + profile snapshot)
 *   - types/auth-store.ts (store API surface)
 *   - contexts/ChatContext.tsx, contexts/ThemeContext.tsx
 *   - routing/routeGuards.tsx, components/layout/Nav.tsx
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

export type UserRole = 'admin' | 'doctor' | 'nurse' | 'registrar' | 'cashier' | 'lab' | 'patient' | string;
export type AuthStatus = 'authenticated' | 'unauthenticated' | 'loading' | 'error' | string;

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
  [key: string]: unknown;
}

export interface AuthState {
  token: string | null;
  profile: UserProfile | null;
  [key: string]: unknown;
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
  [key: string]: unknown;
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
  [key: string]: unknown;
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
  [key: string]: unknown;
}

export interface Role {
  id?: string | number;
  name?: string;
  code?: string;
  permissions?: Permission[];
  [key: string]: unknown;
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
  [key: string]: unknown;
}

export interface LoginCredentials {
  email: string;
  password: string;
  [key: string]: unknown;
}

export interface LoginResponse {
  access_token?: string;
  refresh_token?: string;
  token?: string;
  user?: AuthUser;
  expires_in?: number;
  [key: string]: unknown;
}

export interface TokenPayload {
  sub?: string | number;
  exp?: number;
  iat?: number;
  role?: string;
  roles?: string[];
  [key: string]: unknown;
}

export interface SessionInfo {
  session_id?: string;
  user_id?: string | number;
  ip_address?: string;
  user_agent?: string;
  created_at?: string;
  expires_at?: string;
  is_active?: boolean;
  [key: string]: unknown;
}
