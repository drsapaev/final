import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(__dirname, '../CardiologistPanelUnified.tsx'), 'utf8');
const translations = ['ru', 'en', 'kk', 'uz-Latn', 'uz-Cyrl'];

describe('cardiology visit completion', () => {
  const completionHandler = source.match(/const handleSaveVisit = async\s*\([\s\S]*?\n\s{2}\};/);

  it('builds warnings and the queue payload from the saved EMR fields', () => {
    expect(completionHandler).not.toBeNull();
    expect(completionHandler?.[0]).toContain('emrTextValue(savedEMRData.complaints)');
    expect(completionHandler?.[0]).toContain('emrTextValue(savedEMRData.diagnosis)');
    expect(completionHandler?.[0]).toContain('emrTextValue(savedEMRData.icd10_code)');
    expect(completionHandler?.[0]).toContain('legacyDiagnosis?.icd10_code');
    expect(completionHandler?.[0]).toContain('getCriticalDiagnosisWarning(icd10)');
    expect(completionHandler?.[0]).toMatch(/complaint,\r?\n\s+diagnosis,\r?\n\s+icd10,/);
    expect(completionHandler?.[0]).not.toContain('visitData');
    expect(completionHandler?.[0]).not.toContain('fetch(');
  });

  it('provides a localized read-only status for every supported locale', () => {
    for (const locale of translations) {
      const localeSource = fs.readFileSync(
        path.join(__dirname, `../../i18n/locales/${locale}.ts`),
        'utf8',
      );
      expect(localeSource).toMatch(/cardio_visit_readonly:\s*'[^']+'/);
      expect(localeSource).toMatch(/cardio_visit_back_to_queue:\s*'[^']+'/);
    }
  });
});
