import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
import { normalizeSource } from '../../test/contracts/source-contract-helper';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');
const source = normalizeSource(fs.readFileSync(path.join(ROOT, 'pages/DermatologistPanelUnified.tsx'), 'utf8'));
const translationsSource = normalizeSource(fs.readFileSync(path.join(ROOT, 'i18n/locales/ru.ts'), 'utf8'));

describe('DermatologistPanel STRAT#33 — i18n migration', () => {
  it('imports useTranslation from i18n adapter', () => {
    expect(source).toContain("from '../i18n/useTranslation'");
    expect(source).toContain('useTranslation');
  });
  it('instantiates tI18n via useTranslation()', () => {
    expect(source).toContain("const { t: tI18n } = useTranslation()");
  });
  it('uses i18n keys for confirm dialog', () => {
    // Contract: confirm dialog must use i18n translation keys, not hardcoded strings.
    // The variable name (tI18n vs t alias) is an implementation detail.
    expect(source).toContain("'derma.complete_visit_title'");
    expect(source).toContain("'derma.complete_visit_confirm'");
    expect(source).toContain("'derma.cancel'");
  });
  it('uses i18n keys for notify messages', () => {
    // Contract: notify messages must use i18n translation keys, not hardcoded strings.
    expect(source).toContain("'derma.session_expired'");
    expect(source).toContain("'derma.visit_completed'");
    expect(source).toContain("'derma.prescription_saved'");
    expect(source).toContain("'derma.skin_exam_saved'");
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
