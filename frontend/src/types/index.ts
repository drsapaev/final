// src/types/index.ts
// Phase 0.5 — Single re-export point for all type modules.
// Plan: JS-to-TS-Migration-Plan v3, section 0.5.6
//
// Import patterns:
//   import type { User, Patient } from '@/types';           // ← recommended
//   import type { User, Patient } from '@/types/api';       // ← also fine
//   import type { components } from '@/types/generated/api';// ❌ forbidden (Phase 9 ESLint rule)
//
// ⚠️ DO NOT import directly from '@/types/generated/api' in app code.
//    Add re-exports here or in api.ts instead.

// ============================================================================
// Generated (read-only) — re-exported via api.ts
// ============================================================================
export * from './api';

// ============================================================================
// Manual — backend SSOT mirrors
// ============================================================================
export * from './roles';
export * from './auth';
export * from './auth-store';
export * from './route';

// ============================================================================
// Manual — frontend-only UI types
// ============================================================================
export * from './ui';

// ============================================================================
// Manual — i18next type augmentation
// ============================================================================
export type { TranslateFunction } from './i18n';

// ============================================================================
// Manual — feature-based domain types
// ============================================================================
export * from './features/emr';
export * from './features/queue';
export * from './features/telegram';
export * from './features/lab';
export * from './features/payment';
export * from './features/chat';
export * from './features/notification';
export * from './features/wizard';
export * from './features/analytics';
export * from './features/admin';
