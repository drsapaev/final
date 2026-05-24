import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src');

const DOCTOR_PANEL_FILES = [
  'pages/CardiologistPanelUnified.jsx',
  'pages/DentistPanelUnified.jsx',
  'pages/DermatologistPanelUnified.jsx',
];

const read = (filePath) => fs.readFileSync(path.join(ROOT, filePath), 'utf8');

const extractBlock = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('Doctor panels SSOT contract', () => {
  it('uses registrar queue DTO payment/action fields without all-appointments overlay', () => {
    for (const filePath of DOCTOR_PANEL_FILES) {
      const source = read(filePath);

      expect(source).toContain('/registrar/queues/today');
      expect(source).not.toContain('/registrar/all-appointments');
      expect(source).not.toContain('appointmentMetaMap');
      expect(source).not.toContain('appointmentsDBData');

      expect(source).toContain('payment_status: entry.payment_status');
      expect(source).toContain('payment_type: entry.payment_type');
      expect(source).toContain('available_actions: entry.available_actions || []');
      expect(source).toContain('can_mark_paid: Boolean(entry.can_mark_paid)');
      expect(source).toContain('can_start_visit: Boolean(entry.can_start_visit)');
      expect(source).toContain('can_print_ticket: Boolean(entry.can_print_ticket)');
      expect(source).toContain('can_complete: Boolean(entry.can_complete)');
      expect(source).toContain('can_cancel: Boolean(entry.can_cancel)');
    }
  });

  it('keeps doctor table command visibility backend-owned when rows are missing action fields', () => {
    const table = read('components/tables/EnhancedAppointmentsTable.jsx');
    const actionBlock = extractBlock(
      table,
      'const backendCanPay = getBackendActionAvailability',
      'return (',
    );

    expect(actionBlock).toContain("getBackendActionAvailability(row, 'call', 'can_start_visit')");
    expect(actionBlock).toContain("getBackendActionAvailability(row, 'print', 'can_print_ticket')");
    expect(actionBlock).toContain("getBackendActionAvailability(row, 'complete', 'can_complete')");
    expect(actionBlock).toContain('isDoctorView ? false : rowStatus');
    expect(actionBlock).not.toContain('isDoctorView ?\n                  rowStatus');
    expect(actionBlock).not.toContain("rowPaymentStatus === 'paid' :");
  });

  it('does not introduce BFF-lite endpoints while repairing doctor contracts', () => {
    for (const filePath of DOCTOR_PANEL_FILES) {
      const source = read(filePath);

      expect(source).not.toContain('/api/v1/ui/');
      expect(source).not.toContain('/ui/doctor');
      expect(source).not.toContain('/ui/registrar');
    }
  });
});
