import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabReportHistoryPanel.jsx'),
  'utf8'
);

describe('LabReportHistoryPanel STRAT#21 — i18n migration', () => {
  it('imports t from unified i18n', () => {
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('import { useTranslation }');
  });

  it('uses t() for panel titles', () => {
    expect(source).toContain("t('queue.history_recent_title')");
    expect(source).toContain("t('queue.history_patient_title')");
  });

  it('uses t() for empty-state messages', () => {
    expect(source).toContain("t('queue.history_no_saved')");
    expect(source).toContain("t('queue.history_no_matches')");
  });

  it('uses t() for severity filter labels via key map', () => {
    expect(source).toContain('SEVERITY_FILTER_KEY_MAP');
    expect(source).toContain('queue.history_severity_all');
    expect(source).toContain('queue.history_severity_clean');
    expect(source).toContain('queue.history_severity_flagged');
    expect(source).toContain('queue.history_severity_critical');
  });

  it('uses t() for card labels (patient, report, visit, flags, critical)', () => {
    expect(source).toContain("t('queue.history_patient_number')");
    expect(source).toContain("t('queue.history_report_number')");
    expect(source).toContain("t('queue.history_visit')");
    expect(source).toContain("t('queue.history_no_visit')");
    expect(source).toContain("t('queue.history_flags')");
    expect(source).toContain("t('queue.history_critical')");
  });

  it('does not contain hardcoded Russian strings anymore', () => {
    expect(source).not.toContain("'Недавние лабораторные отчёты'");
    expect(source).not.toContain("'Доступные отчёты пациента'");
    expect(source).not.toContain("'Все'");
    expect(source).not.toContain("'Без флагов'");
    expect(source).not.toContain("'С флагами'");
    expect(source).not.toContain("'Критические'");
    expect(source).not.toContain("'Пациент #'");
    expect(source).not.toContain("'без визита'");
    expect(source).not.toContain("'флагов'");
    expect(source).not.toContain("'критич.'");
  });
});
