// src/types/auth-store.ts
// Phase 0.5 — Auth store API types (minimal, no architecture change).
// Plan: JS-to-TS-Migration-Plan v3, section 0.5.5
//
// SSOT: frontend/src/stores/auth.js (functional pub/sub + localStorage).
// ⚠️ Принцип: Type Migration ≠ Refactoring. Только типы, без смены архитектуры.
//
// Если при типизации выяснится, что API-поверхность store нужно менять —
// остановитесь и обсудите с командой. НЕ переписывайте store в этой фазе.

/**
 * Snapshot of auth state — what subscribers receive.
 * Matches `getState()` return in stores/auth.js.
 */
export interface AuthState {
  token: string | null;
  profile: Record<string, unknown> | null;
}

/**
 * Public API of the auth store.
 * Mirrors the default export of stores/auth.js + backwards-compatible aliases.
 */
export interface AuthStore {
  // Core pub/sub
  subscribe: (fn: (state: AuthState) => void) => () => void;
  getState: () => AuthState;

  // Token management
  getToken: () => string | null;
  setToken: (token: string | null) => void;
  clearToken: () => void;

  // Profile management
  getProfile: (force?: boolean) => Promise<Record<string, unknown> | null>;
  setProfile: (profile: Record<string, unknown> | null) => void;

  // Session validation (cached, debounced against backend /me)
  validateSession: (force?: boolean) => Promise<AuthState>;

  // Backwards-compatible aliases (legacy imports still work)
  // ⚠️ Do not remove these — they're imported across the codebase.
  setAuthToken: (token: string | null) => void;
  getAuthToken: () => string | null;
  clearAuthToken: () => void;
  setAuthProfile: (profile: Record<string, unknown> | null) => void;
  subscribeAuth: (fn: (state: AuthState) => void) => () => void;
}
