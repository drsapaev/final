/**
 * NURSE-V2 N2-5 — i18n contract for the tablet workspace (the STRAT#31
 * panel pattern): every `t('nurse.*')` key used by the tablet sources
 * exists in the RU base locale, and the `nurse` namespace is present in
 * ALL five shipped locales (RU/EN/KK/UZ-Latn/UZ-Cyrl).
 */

import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const NURSE_DIR = path.resolve(__dirname, '..');
const SRC_DIR = path.resolve(NURSE_DIR, '../..');

const SOURCES = [
  'NurseTabletPage.tsx',
  'NurseStationBoard.tsx',
  'NurseServiceList.tsx',
  'NurseWorkplacePicker.tsx',
  'NurseIncompleteDialog.tsx',
  'useNurseServingBoard.ts',
].map((rel) => fs.readFileSync(path.join(NURSE_DIR, rel), 'utf8'));

const LOCALES = ['ru', 'en', 'kk', 'uz-Latn', 'uz-Cyrl'] as const;

const localeSources: Record<(typeof LOCALES)[number], string> = {
  ru: fs.readFileSync(path.join(SRC_DIR, 'i18n/locales/ru.ts'), 'utf8'),
  en: fs.readFileSync(path.join(SRC_DIR, 'i18n/locales/en.ts'), 'utf8'),
  kk: fs.readFileSync(path.join(SRC_DIR, 'i18n/locales/kk.ts'), 'utf8'),
  'uz-Latn': fs.readFileSync(path.join(SRC_DIR, 'i18n/locales/uz-Latn.ts'), 'utf8'),
  'uz-Cyrl': fs.readFileSync(path.join(SRC_DIR, 'i18n/locales/uz-Cyrl.ts'), 'utf8'),
};

function extractKeys(source: string): string[] {
  const keys: string[] = [];
  const re = /['"`](nurse\.[a-z0-9_]+)['"`]/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(source)) !== null) {
    keys.push(match[1]);
  }
  return keys;
}

function hasNurseKey(localeSource: string, key: string): boolean {
  // 'nurse.queue_number' -> namespace block check + key check
  const [, keyName] = key.split('.');
  const namespace = new RegExp('\\bnurse:\\s*\\{');
  const keyRe = new RegExp(`\\b${keyName}\\s*:`);
  return namespace.test(localeSource) && keyRe.test(localeSource);
}

describe('NURSE-V2 N2-5 tablet — i18n contract', () => {
  it('uses the unified useTranslation hook', () => {
    const page = SOURCES[0];
    expect(page).toContain('useTranslation');
  });

  it('every nurse.* key used in sources exists in the RU base locale', () => {
    const used = new Set(SOURCES.flatMap(extractKeys));
    expect(used.size).toBeGreaterThan(30);
    const missing = [...used].filter((key) => !hasNurseKey(localeSources.ru, key));
    expect(missing, `missing in ru.ts: ${missing.join(', ')}`).toEqual([]);
  });

  it.each(LOCALES)('the nurse namespace ships complete in %s.ts', (locale) => {
    for (const source of SOURCES) {
      for (const key of extractKeys(source)) {
        expect(
          hasNurseKey(localeSources[locale], key),
          `${key} missing in ${locale}.ts`,
        ).toBe(true);
      }
    }
  });

  it('the errors.nurse fallback key exists in every locale', () => {
    for (const locale of LOCALES) {
      expect(localeSources[locale]).toMatch(/nurse:\s*\{[^}]*board_unavailable/s);
    }
  });
});
