import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(ROOT, 'pages/DermatologistPanelUnified.tsx'), 'utf8');
const translationsSource = fs.readFileSync(path.join(ROOT, 'i18n/locales/ru.ts'), 'utf8');

describe('DermatologistPanel STRAT#33 — i18n migration', () => {
  it('imports useTranslation from i18n adapter', () => {
    expect(source).toContain("from '../i18n/useTranslation'");
    expect(source).toContain('useTranslation');
  });
  it('instantiates tI18n via useTranslation()', () => {
    expect(source).toContain("const { t: tI18n } = useTranslation()");
  });
  it('uses tI18n() for confirm dialog', () => {
    expect(source).toContain("tI18n('derma.complete_visit_title')");
    expect(source).toContain("tI18n('derma.complete_visit_confirm')");
    expect(source).toContain("tI18n('derma.cancel')");
  });
  it('uses tI18n() for notify messages', () => {
    expect(source).toContain("tI18n('derma.session_expired')");
    expect(source).toContain("tI18n('derma.visit_completed')");
    expect(source).toContain("tI18n('derma.prescription_saved')");
    expect(source).toContain("tI18n('derma.skin_exam_saved')");
  });
  it('does not contain hardcoded Russian notify strings', () => {
    expect(source).not.toContain("notify.error('Сессия истекла");
    expect(source).not.toContain("notify.success('Прием завершен успешно')");
    expect(source).not.toContain("notify.success('Рецепт сохранен успешно!')");
  });
  it('labTranslations has derma.* namespace', () => {
    expect(translationsSource).toContain('derma: {');
    expect(translationsSource).toContain('complete_visit_title:');
    expect(translationsSource).toContain('prescription_saved:');
  });
});
