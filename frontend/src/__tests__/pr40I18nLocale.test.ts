/**
 * PR-40 — Frontend i18n + locale: P0-18 + High-20.
 *
 * Tests for:
 * 1. P0-18: RegistrarPanel uses the same localStorage key as useTranslation
 *    (was 'ui_lang' vs 'language' — language switcher silently broken)
 * 2. High-20: dateUtils and formatCurrency provide a getLocale() helper that
 *    reads the active language, and at least one function uses it
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const REGISTRAR = path.join(ROOT, 'src/pages/RegistrarPanel.tsx');
const DATE_UTILS = path.join(ROOT, 'src/utils/dateUtils.ts');
const FORMAT_CURRENCY = path.join(ROOT, 'src/utils/formatCurrency.ts');

// ---------- 1. P0-18: Unified localStorage key ----------

describe('P0-18: Unified i18n localStorage key', () => {
  const src = fs.readFileSync(REGISTRAR, 'utf-8');

  it('RegistrarPanel does not use the divergent ui_lang localStorage key', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT read from 'ui_lang' (the divergent key)
    expect(stripped).not.toMatch(/localStorage\.getItem\(\s*['"]ui_lang['"]\)/);
  });

  it('RegistrarPanel reads language from the unified key (language or app_language)', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // i18n-unification: react-i18next reads language from its own state, which is
    // persisted to localStorage by i18n/index.js. RegistrarPanel accesses language
    // via useTranslation() hook (destructured as `language` from the hook return).
    // Accept either pattern:
    // (a) useTranslation() destructuring with `language`
    // (b) localStorage.getItem('language' or 'app_language') (legacy direct read)
    const hasUseTranslationLanguage = /const\s*\{[^}]*\blanguage\b[^}]*\}\s*=\s*useTranslation\(\)/.test(stripped);
    const hasLocalStorageRead = /localStorage\.getItem\(\s*['"](?:language|app_language)['"]\)/.test(stripped);
    expect(hasUseTranslationLanguage || hasLocalStorageRead).toBe(true);
  });
});

// ---------- 2. High-20: Locale-aware date/currency formatting ----------

describe('High-20: Locale-aware formatting', () => {
  const dateUtilsSrc = fs.readFileSync(DATE_UTILS, 'utf-8');

  it('dateUtils.js exports a getLocale() helper or reads active language', () => {
    // We accept either:
    // (a) a getLocale() function that reads localStorage
    // (b) a getActiveLocale() function
    // (c) import from useTranslation
    const hasGetLocale = /export\s+(?:const|function)\s+getLocale\b/.test(dateUtilsSrc);
    const hasGetActiveLocale = /export\s+(?:const|function)\s+getActiveLocale\b/.test(dateUtilsSrc);
    const hasUseTranslationImport = /from\s+['"][^'"]*useTranslation['"]/.test(dateUtilsSrc);
    const hasLanguageRead = /localStorage\.getItem\(\s*['"]language['"]/.test(dateUtilsSrc)
      || /localStorage\.getItem\(\s*['"]app_language['"]/.test(dateUtilsSrc);
    expect(hasGetLocale || hasGetActiveLocale || hasUseTranslationImport || hasLanguageRead).toBe(true);
  });

  it('at least one date format function uses the dynamic locale (not hardcoded ru-RU default only)', () => {
    // The old code: formatRegistrarDate(value, locale = 'ru-RU')
    // The fix: formatRegistrarDate(value, locale = getLocale())
    // We check that at least one function uses getLocale() as the default
    const stripped = dateUtilsSrc
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Look for: locale = getLocale() or locale = getActiveLocale()
    // Allow optional TS type annotation between `locale` and `=` (e.g. `locale: string = getLocale()`).
    const usesDynamicLocale = /locale\s*(?::\s*[^=]+)?\s*=\s*(?:getLocale|getActiveLocale)\(\)/.test(stripped);
    expect(usesDynamicLocale).toBe(true);
  });
});
