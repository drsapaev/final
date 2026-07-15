import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabReportAIAnalysis.jsx'),
  'utf8'
);

describe('LabReportAIAnalysis STRAT#22 — i18n migration', () => {
  it('imports t from labTranslations', () => {
    expect(source).toContain("from './utils/labTranslations'");
    expect(source).toContain('import { t }');
  });

  it('uses t() for AI button labels and tooltips', () => {
    expect(source).toContain("t('ai.button_label')");
    expect(source).toContain("t('ai.button_tooltip')");
    expect(source).toContain("t('ai.button_disabled')");
  });

  it('uses t() for dialog title and close button', () => {
    expect(source).toContain("t('ai.dialog_title')");
    expect(source).toContain("t('ai.dialog_close')");
    expect(source).toContain("t('ai.dialog_close_aria')");
  });

  it('uses t() for patient info labels', () => {
    expect(source).toContain("t('ai.patient_label')");
    expect(source).toContain("t('ai.age_label')");
    expect(source).toContain("t('ai.age_years')");
    expect(source).toContain("t('ai.age_unknown')");
    expect(source).toContain("t('ai.gender_label')");
    expect(source).toContain("t('ai.gender_male')");
    expect(source).toContain("t('ai.gender_female')");
    expect(source).toContain("t('ai.gender_other')");
    expect(source).toContain("t('ai.gender_not_set')");
    expect(source).toContain("t('ai.fields_count')");
  });

  it('uses t() for blocked reason messages', () => {
    expect(source).toContain("t('ai.blocked_no_results')");
    expect(source).toContain("t('ai.blocked_no_age')");
    expect(source).toContain("t('ai.blocked_no_gender')");
    expect(source).toContain("t('ai.blocked_generic')");
    expect(source).toContain("t('ai.fill_fields_first')");
    expect(source).toContain("t('ai.missing_age_gender')");
  });

  it('does not contain hardcoded Russian strings anymore', () => {
    expect(source).not.toContain("'AI Интерпретация'");
    expect(source).not.toContain("'Закрыть AI-анализ'");
    expect(source).not.toContain("'Пациент:'");
    expect(source).not.toContain("'Возраст:'");
    expect(source).not.toContain("'Пол:'");
    expect(source).not.toContain("'мужской'");
    expect(source).not.toContain("'женский'");
    expect(source).not.toContain("'Сначала заполните хотя бы один показатель'");
  });
});
