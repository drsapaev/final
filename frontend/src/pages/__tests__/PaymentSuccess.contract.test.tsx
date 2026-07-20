import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const paymentSuccessPath = path.resolve(__dirname, '../PaymentSuccess.tsx');

describe('PaymentSuccess receipt route contract', () => {
  it('uses the backend canonical GET receipt endpoint with format_type query params', () => {
    const source = fs.readFileSync(paymentSuccessPath, 'utf8');

    expect(source).toContain('apiClient.get(`/payments/${paymentId}/receipt`');
    expect(source).toContain('params: { format_type: \'pdf\' }');
    expect(source).not.toContain('apiClient.post(`/payments/${paymentId}/receipt`');
    expect(source).not.toContain('format: \'pdf\'');
  });
});
