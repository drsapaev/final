import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

const source = fs.readFileSync(
  path.join(ROOT, 'pages/CardiologistPanelUnified.jsx'),
  'utf8'
);

const translationsSource = fs.readFileSync(
  path.join(ROOT, 'i18n/locales/ru.js'),
  'utf8'
);

describe('CardiologistPanel STRAT#32 — i18n migration', () => {
  it('imports useTranslation from unified i18n', () => {
    expect(source).toContain("from '../i18n/useTranslation'");
    expect(source).toContain('useTranslation');
  });

  it('instantiates tI18n via useTranslation()', () => {
    expect(source).toContain("const { t: tI18n } = useTranslation()");
  });

  it('uses tI18n() for confirm dialog', () => {
    expect(source).toContain("tI18n('cardio.cancel_appointment_title')");
    expect(source).toContain("tI18n('cardio.cancel_appointment_message'");
    expect(source).toContain("tI18n('cardio.cancel_appointment_confirm')");
    expect(source).toContain("tI18n('cardio.cancel_appointment_cancel')");
  });

  it('uses tI18n() for all notify messages', () => {
    expect(source).toContain("tI18n('cardio.session_expired')");
    expect(source).toContain("tI18n('cardio.select_patient_first')");
    expect(source).toContain("tI18n('cardio.appointment_cancelled')");
    expect(source).toContain("tI18n('cardio.visit_completed')");
    expect(source).toContain("tI18n('cardio.blood_test_saved')");
    expect(source).toContain("tI18n('cardio.ecg_added')");
    expect(source).toContain("tI18n('cardio.settings_saved')");
  });

  it('does not contain hardcoded Russian strings in notify() calls', () => {
    expect(source).not.toContain("notify.error('Сессия истекла");
    expect(source).not.toContain("notify.success('Запись отменена')");
    expect(source).not.toContain("notify.success('Прием завершен успешно')");
    expect(source).not.toContain("notify.success('Анализ крови сохранен успешно')");
    expect(source).not.toContain("notify.success('Настройки сохранены')");
  });

  it('labTranslations has cardio.* namespace with all keys', () => {
    expect(translationsSource).toContain('cardio: {');
    const keys = [
      'cancel_appointment_title', 'cancel_appointment_message',
      'cancel_appointment_confirm', 'cancel_appointment_cancel',
      'session_expired', 'select_patient_first', 'visit_completed',
      'blood_test_saved', 'ecg_added', 'settings_saved',
    ];
    for (const key of keys) {
      expect(translationsSource).toContain(`${key}:`);
    }
  });
});
