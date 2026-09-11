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

  it('allows existing invoices only through backend-authorized providers', () => {
    expect(SOURCE).toContain('getPaymentProviders');
    expect(SOURCE).toContain('provider.features?.registrar_invoice_payment === true');
    expect(SOURCE).toContain('invoiceProviders.some((provider) => provider.code.toLowerCase() === providerCode)');
    expect(SOURCE).toContain('disabled={loading || providersLoading || !providerSupported}');
    expect(SOURCE).toContain('providersLoadFailed');
    expect(SOURCE).not.toContain('createPaymentInvoice');
    expect(SOURCE).not.toContain('handleCreateInvoice');
    expect(SOURCE).not.toContain('value="payme"');
  });

  it('does not reload on every translation wrapper identity change', () => {
    expect(SOURCE).toContain('const tRef = useRef(t);');
    expect(SOURCE).toContain('}, [getPendingInvoices]);');
    expect(SOURCE).toContain('}, [getPaymentProviders]);');
    expect(SOURCE).not.toContain('[getPendingInvoices, t]');
    expect(SOURCE).not.toContain('[getPaymentProviders, t]');
  });
});
