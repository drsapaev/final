import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src/components/payment');

const readPaymentWidget = () =>
  fs.readFileSync(path.join(ROOT, 'PaymentWidget.tsx'), 'utf8').replace(/\r\n/g, '\n');

describe('PaymentWidget backend payment status contract', () => {
  it('polls the canonical backend payment status route via the current payment data ref (CSH-FE-029)', () => {
    const source = readPaymentWidget();

    // CSH-FE-029: the polling path must read the payment from paymentDataRef
    // (currentPaymentData), never a stale closure over paymentData state.
    expect(source).toContain('const currentPaymentData = paymentDataRef.current;');
    expect(source).toContain('apiClient.get(`/payments/${currentPaymentData.payment_id}`)');
    expect(source).not.toContain('apiClient.get(`/payments/${paymentData.payment_id}`)');
    expect(source).not.toContain('apiClient.get(`/payments/${paymentData.payment_id}/status`)');
  });

  it('keeps provider loading on a stable dependency surface (CSH-FE-030)', () => {
    const source = readPaymentWidget();

    // t is unstable per render — it must NOT be a loadProviders dependency.
    expect(source).toContain('}, [currency]);');
    expect(source).not.toContain('}, [currency, t]);');
    // manual provider selection must survive reloads
    expect(source).toContain('setSelectedProvider((current) =>');
  });

  it('treats the polling limit as a monitoring timeout, not a payment failure (CSH-FE-031)', () => {
    const source = readPaymentWidget();

    expect(source).toContain('case \'status_check_timeout\':');
    expect(source).not.toContain('setPaymentStatus(\'failed\');\n      }\n    }, POLLING_INTERVAL_MS);');
  });
});
