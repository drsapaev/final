import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(ROOT, 'pages/DoctorPanel.tsx'), 'utf8');
const translationsSource = fs.readFileSync(path.join(ROOT, 'i18n/locales/ru.js'), 'utf8');

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
