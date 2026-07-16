import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src/components/payment');

const readPaymentWidget = () =>
  fs.readFileSync(path.join(ROOT, 'PaymentWidget.tsx'), 'utf8').replace(/\r\n/g, '\n');

describe('PaymentWidget backend payment status contract', () => {
  it('polls the canonical backend payment status route', () => {
    const source = readPaymentWidget();

    expect(source).toContain('apiClient.get(`/payments/${paymentData.payment_id}`)');
    expect(source).not.toContain('apiClient.get(`/payments/${paymentData.payment_id}/status`)');
  });
});
