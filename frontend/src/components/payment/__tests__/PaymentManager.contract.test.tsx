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
    expect(SOURCE).toContain('const invoiceIdValue = getInvoiceId(invoice);');
    expect(SOURCE).toContain('key={invoiceIdValue}');
    expect(SOURCE).toContain('<span className="invoice-id">№{String(invoiceIdValue ?? \'\')}</span>');
    expect(SOURCE).not.toContain('setCreatedInvoiceId(invoice.id);');
  });

  it('allows existing invoices only through backend-owned actions', () => {
    expect(SOURCE).toContain('invoice.available_actions ?? []');
    expect(SOURCE).toContain('action.action === \'start_online_payment\'');
    expect(SOURCE).toContain('payExistingInvoice(invoice, action)');
    expect(SOURCE).toContain('invoice.remaining_amount ?? invoice.amount ?? 0');
    expect(SOURCE).not.toContain('getPaymentProviders');
    expect(SOURCE).not.toContain('invoiceProviders');
    expect(SOURCE).not.toContain('createPaymentInvoice');
    expect(SOURCE).not.toContain('handleCreateInvoice');
    expect(SOURCE).not.toContain('value="payme"');
  });

  it('does not reload on every translation wrapper identity change', () => {
    expect(SOURCE).toContain('const tRef = useRef(t);');
    expect(SOURCE).toContain('}, [getPendingInvoices]);');
    expect(SOURCE).not.toContain('[getPendingInvoices, t]');
  });
});
