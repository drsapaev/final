import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SOURCE = fs
  .readFileSync(
    path.resolve(process.cwd(), 'src/components/payment/PaymentManager.tsx'),
    'utf8'
  )
  .replace(/\r\n/g, '\n');

describe('PaymentManager invoice DTO contract', () => {
  it('uses backend invoice_id when paying existing pending invoices', () => {
    expect(SOURCE).toContain(
      'const getInvoiceId = (invoice) => invoice?.invoice_id ?? invoice?.id ?? null;'
    );
    expect(SOURCE).toContain('setCreatedInvoiceId(getInvoiceId(invoice));');
    expect(SOURCE).toContain('key={getInvoiceId(invoice)}');
    expect(SOURCE).toContain('<span className="invoice-id">№{getInvoiceId(invoice)}</span>');
    expect(SOURCE).not.toContain('setCreatedInvoiceId(invoice.id);');
  });
});
