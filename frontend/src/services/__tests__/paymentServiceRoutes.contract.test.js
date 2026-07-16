import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const paymentServicePath = path.resolve(__dirname, '../payment.ts');

describe('paymentService receipt route contract', () => {
  it('uses the backend canonical GET receipt endpoint with format_type query params', () => {
    const source = fs.readFileSync(paymentServicePath, 'utf8');

    expect(source).toContain('api.get(`/payments/${paymentId}/receipt`');
    expect(source).toContain('params: { format_type: format }');
    expect(source).not.toContain('api.post(`/payments/${paymentId}/receipt`');
    expect(source).not.toContain('format\\n      });');
  });
});
