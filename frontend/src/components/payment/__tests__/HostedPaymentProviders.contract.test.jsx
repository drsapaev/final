import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src/components/payment');

const readProvider = (fileName) =>
  fs.readFileSync(path.join(ROOT, fileName), 'utf8').replace(/\r\n/g, '\n');

describe('hosted payment provider ticket contract', () => {
  // HIGH #5 fix: PaymentClick.jsx and PaymentPayMe.jsx were unified into
  // PaymentProviderDialog.jsx. The wrappers preserve the public API and
  // CSS classes; the source of truth (and the api-calls / ticket-parsing
  // patterns the contract verifies) now lives in PaymentProviderDialog.jsx.
  const PROVIDER_FILES = ['PaymentProviderDialog.tsx'];

  for (const fileName of PROVIDER_FILES) {
    it(`${fileName} uses the authenticated api client for protected registrar invoice endpoints`, () => {
      const source = readProvider(fileName);

      expect(source).toContain('import { api } from \'../../api/client\'');
      expect(source).toContain('api.post(\'/registrar/invoice/init-payment\'');
      expect(source).toContain('api.get(`/registrar/invoice/${invoiceId}/status`');
      expect(source).not.toContain('fetch(`${API_BASE}/registrar/invoice/init-payment');
      expect(source).not.toContain('fetch(`${API_BASE}/registrar/invoice/${invoiceId}/status');
      expect(source).not.toContain('response.json()');
    });

    it(`${fileName} prints only backend-provided tickets`, () => {
      const source = readProvider(fileName);

      expect(source).toContain('Array.isArray(data.print_tickets) ? data.print_tickets : []');
      expect(source).toContain('setPrintTickets(tickets)');
      expect(source).toContain('setShowTicketPrinter(tickets.length > 0)');

      expect(source).not.toContain('mockTickets');
      expect(source).not.toContain('cardiology_common');
      expect(source).not.toContain('queue_number: 15');
      expect(source).not.toContain('queue_number: 8');
      expect(source).not.toContain('loadPrintTickets');
    });
  }

  it('PaymentClick and PaymentPayMe are thin wrappers around PaymentProviderDialog', () => {
    for (const fileName of ['PaymentClick.tsx', 'PaymentPayMe.tsx']) {
      const source = readProvider(fileName);
      expect(source).toContain('import PaymentProviderDialog from \'./PaymentProviderDialog\'');
      // Wrappers must NOT contain api calls directly — that logic lives in the dialog.
      expect(source).not.toContain('api.post');
      expect(source).not.toContain('api.get');
    }
  });
});
