import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(ROOT, 'pages/DentistPanelUnified.jsx'), 'utf8');
const translationsSource = fs.readFileSync(path.join(ROOT, 'components/laboratory/utils/labTranslations.js'), 'utf8');

describe('DentistPanel STRAT#34 — i18n migration', () => {
  it('imports useTranslation from i18n adapter', () => {
    expect(source).toContain('from \'../i18n/adapter\'');
    expect(source).toContain('useTranslation');
  });
  it('uses tI18n() for notify messages', () => {
    expect(source).toContain('tI18n(\'dental.session_expired\')');
    expect(source).toContain('tI18n(\'dental.visit_completed\')');
    expect(source).toContain('tI18n(\'dental.icd_added_from_ai\')');
  });
  it('does not contain hardcoded Russian notify strings', () => {
    expect(source).not.toContain('notify.error(\'Сессия истекла');
    expect(source).not.toContain('notify.success(\'Приём завершён успешно\')');
  });
  it('labTranslations has dental.* namespace', () => {
    expect(translationsSource).toContain('dental: {');
    expect(translationsSource).toContain('visit_completed:');
  });
});
