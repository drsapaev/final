import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { normalizeSource } from '../../../test/contracts/source-contract-helper';

const SOURCE = normalizeSource(fs
  .readFileSync(
    path.resolve(process.cwd(), 'src/components/payment/PaymentManager.tsx'),
    'utf8'
  )
  .replace(/\r\n/g, '\n'));

describe('PaymentManager invoice DTO contract', () => {
  it('uses backend invoice_id when paying existing pending invoices', () => {
    // Contract: getInvoiceId must prefer backend invoice_id, fall back to id.
    // The function body is split across lines after TS migration — check key parts.
    expect(SOURCE).toContain('const getInvoiceId = (invoice)');
    expect(SOURCE).toContain('invoice?.invoice_id');
    expect(SOURCE).toContain('invoice?.id');
    expect(SOURCE).toContain('setCreatedInvoiceId(getInvoiceId(invoice));');
    expect(SOURCE).toContain('key={getInvoiceId(invoice)}');
    expect(SOURCE).toContain('<span className="invoice-id">№{getInvoiceId(invoice)}</span>');
    expect(SOURCE).not.toContain('setCreatedInvoiceId(invoice.id);');
  });
});
