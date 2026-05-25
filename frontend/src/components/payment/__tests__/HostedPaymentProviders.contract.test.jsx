import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src/components/payment');

const readProvider = (fileName) =>
  fs.readFileSync(path.join(ROOT, fileName), 'utf8').replace(/\r\n/g, '\n');

describe('hosted payment provider ticket contract', () => {
  for (const fileName of ['PaymentClick.jsx', 'PaymentPayMe.jsx']) {
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
});
