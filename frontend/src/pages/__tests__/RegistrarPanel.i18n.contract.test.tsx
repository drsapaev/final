import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

const source = fs.readFileSync(
  path.join(ROOT, 'pages/RegistrarPanel.tsx'),
  'utf8'
);

const translationsSource = fs.readFileSync(
  path.join(ROOT, 'i18n/locales/ru.ts'),
  'utf8'
);

describe('RegistrarPanel STRAT#30 — i18n migration', () => {
  it('imports useTranslation from unified i18n', () => {
    // i18n-unification: now imports from unified useTranslation, not adapter shim
    expect(source).toContain("from '../i18n/useTranslation'");
    expect(source).toContain('useTranslation');
  });

  it('instantiates tI18n via useTranslation()', () => {
    // i18n-unification: also destructures `language` for locale-aware formatting
    expect(source).toContain('const { t: tI18n');
    expect(source).toContain('useTranslation()');
  });

  it('uses tI18n() for all confirm dialog titles', () => {
    expect(source).toContain("tI18n('registrar.send_to_cabinet_title')");
    expect(source).toContain("tI18n('registrar.complete_visit_title')");
    expect(source).toContain("tI18n('registrar.postpone_tomorrow_title')");
    expect(source).toContain("tI18n('registrar.postpone_date_title')");
  });

  it('uses tI18n() for confirm dialog confirmLabel and cancelLabel', () => {
    expect(source).toContain("tI18n('registrar.send_to_cabinet_confirm')");
    expect(source).toContain("tI18n('registrar.complete_visit_confirm')");
    expect(source).toContain("tI18n('registrar.postpone_tomorrow_confirm')");
    expect(source).toContain("tI18n('registrar.postpone_date_confirm')");
    expect(source).toContain("tI18n('registrar.cancel')");
  });

  it('uses tI18n() with params for confirm dialog messages', () => {
    expect(source).toContain("tI18n('registrar.send_to_cabinet_message', { name: inCabinetName })");
    expect(source).toContain("tI18n('registrar.complete_visit_message', { name: completeName })");
    expect(source).toContain("tI18n('registrar.postpone_tomorrow_message')");
  });

  it('uses tI18n() for all notify messages', () => {
    expect(source).toContain("tI18n('registrar.sent_to_cabinet')");
    expect(source).toContain("tI18n('registrar.visit_completed')");
    expect(source).toContain("tI18n('registrar.appointment_created')");
    expect(source).toContain("tI18n('registrar.visit_postponed')");
    expect(source).toContain("tI18n('registrar.no_visit_for_postpone')");
    expect(source).toContain("tI18n('registrar.select_postpone_date')");
    expect(source).toContain("tI18n('registrar.invalid_date_format')");
    expect(source).toContain("tI18n('registrar.invalid_time_format')");
    expect(source).toContain("tI18n('registrar.cannot_postpone_past')");
    expect(source).toContain("tI18n('registrar.backend_unavailable')");
  });

  it('does not contain hardcoded Russian strings in confirm() calls anymore', () => {
    expect(source).not.toContain("title: 'Отправить в кабинет'");
    expect(source).not.toContain("title: 'Завершение приёма'");
    expect(source).not.toContain("title: 'Перенос на завтра'");
    expect(source).not.toContain("title: 'Перенос на другую дату'");
    expect(source).not.toContain("confirmLabel: 'Отправить'");
    expect(source).not.toContain("confirmLabel: 'Завершить'");
    expect(source).not.toContain("confirmLabel: 'Перенести'");
    expect(source).not.toContain("cancelLabel: 'Отмена'");
  });

  it('labTranslations has registrar.* namespace with all keys', () => {
    expect(translationsSource).toContain('registrar: {');
    const keys = [
      'send_to_cabinet_title', 'send_to_cabinet_message', 'send_to_cabinet_confirm',
      'complete_visit_title', 'complete_visit_message', 'complete_visit_confirm',
      'postpone_tomorrow_title', 'postpone_tomorrow_message', 'postpone_tomorrow_description',
      'postpone_tomorrow_confirm', 'postpone_date_title', 'postpone_date_confirm',
      'cancel', 'sent_to_cabinet', 'visit_completed', 'appointment_created',
      'visit_postponed', 'visit_postponed_date', 'no_visit_for_postpone',
      'select_postpone_date', 'invalid_date_format', 'invalid_time_format',
      'cannot_postpone_past', 'backend_unavailable',
    ];
    for (const key of keys) {
      expect(translationsSource).toContain(`${key}:`);
    }
  });
});
