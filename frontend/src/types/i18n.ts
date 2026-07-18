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
    resources: {
      ru: Record<string, unknown>;
      en: Record<string, unknown>;
      kk: Record<string, unknown>;
      'uz-Latn': Record<string, unknown>;
      'uz-Cyrl': Record<string, unknown>;
    };
    returnNull: false;
  }
}

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
}

export type TranslateFunction = (
  key: string,
  options?: Record<string, unknown>,
) => string;

export type { DefaultNamespace };
