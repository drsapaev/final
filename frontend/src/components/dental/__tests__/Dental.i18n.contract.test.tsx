import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');
const translationsSource = fs.readFileSync(path.join(ROOT, 'i18n/locales/ru.ts'), 'utf8');

const files = ['DentalPriceManager', 'DentalVisitScreen', 'DiagnosisForm', 'ExaminationForm', 'PatientCard', 'PhotoArchive', 'ToothModal', 'TreatmentPlanner', 'VisitProtocol'];

describe('Dental components STRAT#38 — i18n migration', () => {
  for (const name of files) {
    const source = fs.readFileSync(path.join(ROOT, `components/dental/${name}.tsx`), 'utf8');
    it(`${name} has no hardcoded Russian notify strings`, () => {
      expect(source).not.toMatch(/notify\.\w+\('[А-Яа-я]/);
    });
  }
  it('labTranslations has dental2.* namespace', () => {
    expect(translationsSource).toContain('dental2: {');
    expect(translationsSource).toContain('price_fields_required:');
    expect(translationsSource).toContain('visit_protocol_save_failed:');
  });
});
