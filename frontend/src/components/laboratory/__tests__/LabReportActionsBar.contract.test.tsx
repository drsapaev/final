import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabReportActionsBar.tsx'),
  'utf8'
);

const translationsSource = fs.readFileSync(
  path.join(ROOT, 'i18n/locales/ru.ts'),
  'utf8'
);

describe('LabReportActionsBar STRAT#5 — i18n migration', () => {
  it('imports useTranslation from unified i18n', () => {
    // i18n-unification: now uses unified useTranslation hook from i18n/useTranslation
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('useTranslation');
  });

  it('uses t() for all button labels (no hardcoded Russian strings)', () => {
    // Все 5 button label pairs должны использовать t()
    expect(source).toContain("t('actions.saving')");
    expect(source).toContain("t('actions.save_draft')");
    expect(source).toContain("t('actions.finalizing')");
    expect(source).toContain("t('actions.finalize')");
    expect(source).toContain("t('actions.revising')");
    expect(source).toContain("t('actions.revise')");
    expect(source).toContain("t('actions.printing')");
    expect(source).toContain("t('actions.print')");
    expect(source).toContain("t('actions.notifying')");
    expect(source).toContain("t('actions.notify_patient')");
  });

  it('uses t() for title attribute on Revise button', () => {
    expect(source).toContain("title={t('actions.revise_title')}");
  });

  it('does not contain hardcoded Russian button labels anymore', () => {
    // Ранее эти строки были захардкожены в JSX
    expect(source).not.toContain("'Сохраняю...'");
    expect(source).not.toContain("'Сохранить черновик'");
    expect(source).not.toContain("'Утверждаю...'");
    expect(source).not.toContain("'Утвердить'");
    expect(source).not.toContain("'Создаю...'");
    expect(source).not.toContain("'Исправленная версия'");
    expect(source).not.toContain("'Отправляю...'");
    expect(source).not.toContain("'Печать результата'");
    expect(source).not.toContain("'Отправить пациенту'");
    expect(source).not.toContain('title="Создать исправленную версию отчёта"');
  });

  it('labTranslations has all actions.* keys used by ActionsBar', () => {
    // Проверяем, что все keys, которые использует компонент, существуют в словаре
    const keys = [
      'save_draft', 'saving',
      'finalize', 'finalizing',
      'revise', 'revising', 'revise_title',
      'print', 'printing',
      'notify_patient', 'notifying',
    ];
    for (const key of keys) {
      expect(translationsSource).toContain(`${key}:`);
    }
  });

  it('has STRAT#5 marker in JSDoc', () => {
    expect(source).toContain('STRAT#5');
  });
});
