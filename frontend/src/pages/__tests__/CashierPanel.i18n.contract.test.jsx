import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

const source = fs.readFileSync(
  path.join(ROOT, 'pages/CashierPanel.jsx'),
  'utf8'
);

const translationsSource = fs.readFileSync(
  path.join(ROOT, 'i18n/locales/ru.js'),
  'utf8'
);

describe('CashierPanel STRAT#31 — i18n migration', () => {
  it('imports useTranslation from i18n adapter', () => {
    expect(source).toContain("from '../i18n/adapter'");
    expect(source).toContain('useTranslation');
  });

  it('instantiates tI18n via useTranslation()', () => {
    expect(source).toContain("const { t: tI18n } = useTranslation()");
  });

  it('uses tI18n() for confirm dialog', () => {
    expect(source).toContain("tI18n('cashier.confirm_payment_title')");
    expect(source).toContain("tI18n('cashier.confirm_payment_message')");
    expect(source).toContain("tI18n('cashier.confirm_payment_description')");
    expect(source).toContain("tI18n('cashier.confirm_payment_confirm')");
    expect(source).toContain("tI18n('cashier.cancel')");
  });

  it('uses tI18n() for all notify messages', () => {
    expect(source).toContain("tI18n('cashier.session_expired')");
    expect(source).toContain("tI18n('cashier.cancel_reason_required')");
    expect(source).toContain("tI18n('cashier.payment_cancelled')");
    expect(source).toContain("tI18n('cashier.refund_fields_required')");
    expect(source).toContain("tI18n('cashier.no_payment_for_receipt')");
    expect(source).toContain("tI18n('cashier.print_dialog_opened')");
    expect(source).toContain("tI18n('cashier.print_dialog_failed')");
    expect(source).toContain("tI18n('cashier.session_extending')");
  });

  it('does not contain hardcoded Russian strings in confirm() calls anymore', () => {
    expect(source).not.toContain("title: 'Подтверждение платежа'");
    expect(source).not.toContain("confirmLabel: 'Принять'");
    expect(source).not.toContain("cancelLabel: 'Отмена'");
  });

  it('does not contain hardcoded Russian strings in notify() calls anymore', () => {
    expect(source).not.toContain("notify.error('Сессия истекла");
    expect(source).not.toContain("notify.warning('Укажите причину отмены");
    expect(source).not.toContain("notify.info('Платёж отменён')");
    expect(source).not.toContain("notify.warning('Укажите сумму возврата");
    expect(source).not.toContain("notify.error('Не удалось определить платеж");
    expect(source).not.toContain("notify.success('Открыт диалог печати");
    expect(source).not.toContain("notify.warning('Диалог печати не открылся");
    expect(source).not.toContain("notify.info('Продлеваем сессию...')");
  });

  it('labTranslations has cashier.* namespace with all keys', () => {
    expect(translationsSource).toContain('cashier: {');
    const keys = [
      'confirm_payment_title', 'confirm_payment_message', 'confirm_payment_description',
      'confirm_payment_confirm', 'cancel',
      'session_expired', 'cancel_reason_required', 'payment_cancelled',
      'refund_fields_required', 'no_payment_for_receipt',
      'print_dialog_opened', 'print_dialog_failed', 'session_extending',
    ];
    for (const key of keys) {
      expect(translationsSource).toContain(`${key}:`);
    }
  });
});
