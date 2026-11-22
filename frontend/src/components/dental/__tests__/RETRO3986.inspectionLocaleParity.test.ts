/**
 * RETRO-3986-02 (post-merge review 4000) — the inspection-only banner is
 * translated outside Russian.
 *
 * Red-first: on pre-fix sources `dental2.tooth_inspection_only` carried the
 * identical Russian copy in en/kk/uz-Cyrl/uz-Latn (en.ts, kk.ts, uz-Cyrl.ts,
 * uz-Latn.ts) — an English/Kazakh/Uzbek UI showed a Russian banner (the
 * parity was "complete" only in the sense that no raw key leaked).
 *
 * Post-fix contract: every non-ru locale carries ITS OWN translation for
 * this key — value differs from the ru copy, is non-empty, and interpolates
 * no placeholder (the banner is a static sentence).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = path.resolve(__dirname, '../../../i18n/locales');

const readLocale = (loc: string) =>
  fs.readFileSync(path.join(LOCALES_DIR, `${loc}.ts`), 'utf8').replace(/\r\n/g, '\n');

/** Extract the tooth_inspection_only literal from the flat dental2 block. */
function extractValue(source: string): string {
  const match = source.match(/tooth_inspection_only:\s*(['"])([\s\S]*?)\1/);
  expect(match).not.toBeNull();
  return match![2];
}

const ruValue = extractValue(readLocale('ru'));

describe('RETRO-3986-02: dental2.tooth_inspection_only is translated per locale', () => {
  it.each(['en', 'kk', 'uz-Cyrl', 'uz-Latn'])(
    '%s no longer reuses the Russian copy',
    (loc) => {
      const value = extractValue(readLocale(loc));
      expect(value.trim()).not.toBe('');
      expect(value).not.toBe(ruValue);
      // static sentence — no leftover interpolation braces from the repair
      expect(value).not.toContain('{');
      expect(value).not.toContain('}');
    },
  );

  it('CONTROL: the ru copy is intact and the sibling en block is translated', () => {
    expect(ruValue).toContain('осмотра');
    expect(extractValue(readLocale('en'))).toMatch(/inspection mode/i);
  });
});
