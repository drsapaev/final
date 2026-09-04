import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

// PR-UI-15-5: notify-message handlers (incl. dental.visit_completed) moved
// verbatim to pages/dentist/useDentistActions.ts — the dentist i18n contract
// surface is the union of the panel and its extracted modules (same pattern
// as the safety contract + DoctorPanels.contract.test.tsx).
const readDentistModules = () => {
  const parts: string[] = [];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === '__tests__') continue;
        walk(full);
      } else if (/\.tsx?$/.test(entry.name)) {
        parts.push(fs.readFileSync(full, 'utf8'));
      }
    }
  };
  const dentistDir = path.join(ROOT, 'pages/dentist');
  if (fs.existsSync(dentistDir)) walk(dentistDir);
  return parts.join('\n');
};

const source = (
  fs.readFileSync(path.join(ROOT, 'pages/DentistPanelUnified.tsx'), 'utf8') +
  '\n' +
  readDentistModules()
).replace(/\r\n/g, '\n');
const translationsSource = fs.readFileSync(path.join(ROOT, 'i18n/locales/ru.ts'), 'utf8');

describe('DentistPanel STRAT#34 — i18n migration', () => {
  it('imports useTranslation from i18n adapter', () => {
    expect(source).toContain("from '../i18n/useTranslation'");
    expect(source).toContain('useTranslation');
  });
  it('uses tI18n() for notify messages', () => {
    expect(source).toContain("tI18n('dental.session_expired')");
    expect(source).toContain("tI18n('dental.visit_completed')");
    expect(source).toContain("tI18n('dental.icd_added_from_ai')");
  });
  it('does not contain hardcoded Russian notify strings', () => {
    expect(source).not.toContain("notify.error('Сессия истекла");
    expect(source).not.toContain("notify.success('Приём завершён успешно')");
  });
  it('labTranslations has dental.* namespace', () => {
    expect(translationsSource).toContain('dental: {');
    expect(translationsSource).toContain('visit_completed:');
  });
});
