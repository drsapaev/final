import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');
// PR-UI-15-1: status presentation maps moved verbatim to
// pages/doctor/doctorStatus.ts. PR-UI-15-2: tab JSX moved verbatim to
// pages/doctor/views/* — the i18n surface is the union of the panel and its
// extracted modules (same pattern as registrar/cashier contract tests
// reading extracted hook/view files).
const readDoctorSource = () => {
  const parts = [fs.readFileSync(path.join(ROOT, 'pages/DoctorPanel.tsx'), 'utf8')];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === '__tests__') continue;
        walk(full);
      } else if (/\.(ts|tsx)$/.test(entry.name)) {
        parts.push(fs.readFileSync(full, 'utf8'));
      }
    }
  };
  walk(path.join(ROOT, 'pages/doctor'));
  return parts.join('\n');
};
const source = readDoctorSource();
const translationsSource = fs.readFileSync(path.join(ROOT, 'i18n/locales/ru.ts'), 'utf8');

describe('DoctorPanel STRAT#35 — i18n migration', () => {
  it('imports useTranslation from unified i18n', () => {
    // i18n-unification: now imports useTranslation from unified, not adapter
    expect(source).toContain("from '../i18n/useTranslation'");
    expect(source).toContain('useTranslation');
  });
  it('uses t() for status labels', () => {
    expect(source).toContain("t('doctor.status_active')");
    expect(source).toContain("t('doctor.status_waiting')");
    expect(source).toContain("t('doctor.status_completed')");
  });
  it('uses t() for UI labels', () => {
    expect(source).toContain("t('doctor.patients_not_found')");
    expect(source).toContain("t('doctor.appointments_not_loaded')");
    expect(source).toContain("t('doctor.patient_default')");
  });
  it('labTranslations has doctor.* namespace', () => {
    expect(translationsSource).toContain('doctor: {');
    expect(translationsSource).toContain('status_active:');
    expect(translationsSource).toContain('patients_not_found:');
  });
});
