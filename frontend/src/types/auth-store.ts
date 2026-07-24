// src/types/auth-store.ts
// Phase 0.5 — Auth store API types (minimal, no architecture change).
// Plan: JS-to-TS-Migration-Plan v3, section 0.5.5
//
// SSOT: frontend/src/stores/auth.js (functional pub/sub + localStorage).
// ⚠️ Принцип: Type Migration ≠ Refactoring. Только типы, без смены архитектуры.
//
// Если при типизации выяснится, что API-поверхность store нужно менять —
// остановитесь и обсудите с командой. НЕ переписывайте store в этой фазе.
//
// Wave 3 consolidation: AuthState and UserProfile are now imported from
// '@/types/domain/auth' as the single source of truth. This file only
// re-exports them for backwards compatibility with callers that still
// import from '@/types/auth-store'. New code should import from the domain
// layer directly.

import type { AuthState, UserProfile } from './domain/auth';

// Re-export so existing `import type { AuthState } from '@/types/auth-store'`
// keeps working without churn.
export type { AuthState, UserProfile } from './domain/auth';

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
  getProfile: (force?: boolean) => Promise<UserProfile | null>;
  setProfile: (profile: UserProfile | null) => void;

  // Session validation (cached, debounced against backend /me)
  validateSession: (force?: boolean) => Promise<AuthState>;

  // Backwards-compatible aliases (legacy imports still work)
  // ⚠️ Do not remove these — they're imported across the codebase.
  setAuthToken: (token: string | null) => void;
  getAuthToken: () => string | null;
  clearAuthToken: () => void;
  setAuthProfile: (profile: UserProfile | null) => void;
  subscribeAuth: (fn: (state: AuthState) => void) => () => void;
}
