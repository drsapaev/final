/**
 * RETRO-3994-01 (post-merge review 4000) — the signed/amended provenance
 * tooltip must render the FORMATTED TIMESTAMP through real i18next
 * interpolation, not a raw JS-expression-style placeholder.
 *
 * Red-first: on pre-fix locales the value was
 * `'Подписана {formatAbsoluteTime(lastSaved)}'` in ALL five locales while
 * the component passes `{ lastSaved: formatAbsoluteTime(lastSaved) }` —
 * the app's single-brace interpolation (`i18n/index.ts` prefix/suffix
 * `{}`) can only substitute `{lastSaved}`; `{formatAbsoluteTime(...)}` is
 * a JS-expression spelling i18next cannot resolve, so the tooltip showed
 * the literal string with braces. The sibling key
 * `esi_sohraneno_v_absolutetime` ('Сохранено в {absoluteTime}') proves the
 * config itself works — the spelling was the defect. The PR's own test
 * mocked `t`, so real interpolation was never exercised.
 *
 * Post-fix contract (verified against the REAL ru bundle, no `t` mock):
 *  - the signed tooltip contains the formatted time and no `{`/`}`;
 *  - every locale's value uses the `{lastSaved}` placeholder spelling;
 *  - the source carries no `{formatAbsoluteTime(` spelling anywhere.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import React from 'react';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

// REAL interpolation: wrap the app's actual i18n singleton (ru bundle).
vi.mock('@/i18n/useTranslation', async () => {
  const { default: realI18n } = await import('@/i18n');
  return {
    useTranslation: () => ({
      t: (key: string, params?: Record<string, unknown>) =>
        realI18n.t(key, params) as unknown as string,
      i18n: realI18n,
      language: realI18n.language,
      setLanguage: () => {},
      availableLanguages: [],
      ready: true,
    }),
  };
});

import EMRStatusIndicator from '../EMRStatusIndicator';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = path.resolve(__dirname, '../../../i18n/locales');

const LOCALES = ['ru', 'en', 'kk', 'uz-Cyrl', 'uz-Latn'];

const readLocale = (loc: string) =>
  fs.readFileSync(path.join(LOCALES_DIR, `${loc}.ts`), 'utf8').replace(/\r\n/g, '\n');

function extractValue(source: string, key: string): string {
  const match = source.match(new RegExp(`${key}:\\s*(['"])([\\s\\S]*?)\\1`));
  expect(match).not.toBeNull();
  return match![2];
}

describe('RETRO-3994-01: signed provenance tooltip interpolates the timestamp', () => {
  it('signed tooltip renders the formatted time — no raw placeholder, no braces', () => {
    const { container } = render(
      <EMRStatusIndicator isSigned lastSaved="2026-11-10T12:00:00Z" />,
    );
    const title = container.firstElementChild?.getAttribute('title') || '';
    expect(title).not.toBe('');
    expect(title).not.toContain('{');
    expect(title).not.toContain('}');
    expect(title).not.toContain('formatAbsoluteTime');
    // a real formatted time rendered (ru-RU: "12:00:00")
    expect(title).toMatch(/\d{2}:\d{2}/);
  });

  it('amended tooltip renders the formatted time too', () => {
    const { container } = render(
      <EMRStatusIndicator isAmended lastSaved="2026-11-10T12:00:00Z" />,
    );
    const title = container.firstElementChild?.getAttribute('title') || '';
    expect(title).toMatch(/\d{2}:\d{2}/);
    expect(title).not.toContain('{');
  });

  it.each(LOCALES)(
    '%s uses the {lastSaved} placeholder spelling for esi_podpisana_formatabsolutetime',
    (loc) => {
      const value = extractValue(
        readLocale(loc),
        'esi_podpisana_formatabsolutetime',
      );
      expect(value).toContain('{lastSaved}');
      expect(value).not.toContain('formatAbsoluteTime');
      expect(value).not.toContain('{{');
    },
  );

  it('CONTROL: the sibling absolute-time key keeps interpolating', () => {
    const { container } = render(
      <EMRStatusIndicator isSigned={false} lastSaved="2026-11-10T12:00:00Z" />,
    );
    // A plain saved document falls into the relative/absolute save branch —
    // its tooltip also must not leak raw braces.
    const title = container.firstElementChild?.getAttribute('title') || '';
    expect(title).not.toContain('{formatAbsoluteTime');
  });
});
