// src/types/i18n.ts
// Phase 0.5 — i18next type augmentation.
// Plan: JS-to-TS-Migration-Plan v3, section 8.2
//
// This file is imported once at app entry (main.tsx) to enable type-safe `t()`.
// Locale files are migrated .js → .ts with `as const` in Phase 8; until then,
// we use loose typing (`string` keys) to avoid blocking Phase 0.5.
//
// After Phase 8 lands, replace `Record<string, unknown>` with the actual
// `typeof import('../i18n/locales/ru')['default']` for full key autocompletion.

import type { DefaultNamespace } from 'i18next';

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'ru';
    // Phase 8 will tighten this to `typeof import('../i18n/locales/ru')['default']`.
    // For now, accept any string key — i18next typing is permissive.
    resources: {
      ru: Record<string, unknown>;
      en: Record<string, unknown>;
      kk: Record<string, unknown>;
      'uz-Latn': Record<string, unknown>;
      'uz-Cyrl': Record<string, unknown>;
    };
    // Allow flat string keys like 'misc.foo' without locale prefix.
    // react-i18next's strict TFunction requires template-literal keys
    // matching resource paths; this override makes t() accept any string.
    returnNull: false;
  }
}

// Override react-i18next's useTranslation hook to return a permissive t()
// that accepts any string key — matching the project's flat-key convention
// (e.g. t('misc.save'), t('cardio.cardio_panel_unit_mgdl')).
declare module 'react-i18next' {
  interface TypeOptions {
    defaultNS: 'ru';
    resources: {
      ru: Record<string, unknown>;
      en: Record<string, unknown>;
      kk: Record<string, unknown>;
      'uz-Latn': Record<string, unknown>;
      'uz-Cyrl': Record<string, unknown>;
    };
  }
  // Override useTranslation to return a permissive t() that accepts any string key
  function useTranslation(ns?: string | string[], options?: Record<string, unknown>): {
    t: (key: string, options?: Record<string, unknown>) => string;
    i18n: any;
    ready: boolean;
    language: string;
    languages: string[];
  };
}

/**
 * Translate function signature, used for module-level helpers that take `t` as
 * a parameter (e.g. formatTimeAgo(date, t)).
 *
 * Matches the subset of i18next's TFunction that the frontend actually uses.
 */
export type TranslateFunction = (
  key: string,
  options?: Record<string, unknown>,
) => string;

export type { DefaultNamespace };
