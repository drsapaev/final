/**
 * Domain types for authentication, authorization, and user management.
 * Used by auth store, AuthContext, LoginForm, UserManagement, and
 * security-related hooks/components.
 */

export type UserRole = 'admin' | 'doctor' | 'nurse' | 'registrar' | 'cashier' | 'lab' | 'patient' | string;
export type AuthStatus = 'authenticated' | 'unauthenticated' | 'loading' | 'error' | string;

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

export interface AuthState {
  user: AuthUser | null;
  token: string | null;
  refreshToken: string | null;
  status: AuthStatus;
  error: string | null;
  isAuthenticated: boolean;
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
