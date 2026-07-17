import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');
const translationsSource = fs.readFileSync(path.join(ROOT, 'i18n/locales/ru.js'), 'utf8');

describe('Payment components STRAT#39 — i18n migration', () => {
  it('PaymentProviderDialog has no hardcoded Russian notify', () => {
    const source = fs.readFileSync(path.join(ROOT, 'components/payment/PaymentProviderDialog.tsx'), 'utf8');
    expect(source).not.toMatch(/notify\.\w+\('[А-Яа-я]/);
  });
  it('CashPaymentModal has no hardcoded Russian notify', () => {
    const source = fs.readFileSync(path.join(ROOT, 'components/payment/CashPaymentModal.tsx'), 'utf8');
    expect(source).not.toMatch(/notify\.\w+\('[А-Яа-я]/);
  });
  it('RefundRequestsTable has no hardcoded Russian strings', () => {
    const source = fs.readFileSync(path.join(ROOT, 'components/cashier/RefundRequestsTable.tsx'), 'utf8');
    expect(source).not.toMatch(/notify\.\w+\('[А-Яа-я]/);
    expect(source).not.toMatch(/title: '[А-Яа-я]/);
  });
  it('labTranslations has payment.* namespace', () => {
    expect(translationsSource).toContain('payment: {');
    expect(translationsSource).toContain('timeout:');
    expect(translationsSource).toContain('col_patient:');
  });
});
