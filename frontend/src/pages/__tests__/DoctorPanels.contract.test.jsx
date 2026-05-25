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
    expect(actionBlock).toContain('const canPay = !isDoctorView && backendCanPay === true');
    expect(actionBlock).toContain('const canCall = backendCanCall === true');
    expect(actionBlock).toContain('const canPrint = backendCanPrint === true');
    expect(actionBlock).toContain('const canComplete = backendCanComplete === true');
    expect(actionBlock).not.toContain('rowStatus');
    expect(actionBlock).not.toContain('rowPaymentStatus');
    expect(actionBlock).not.toContain('isDoctorView ?\n                  rowStatus');
    expect(actionBlock).not.toContain("rowPaymentStatus === 'paid' :");
  });

  it('routes start visit commands through the doctor command surface', () => {
    for (const filePath of DOCTOR_PANEL_FILES) {
      const source = read(filePath);

      expect(source).toContain('/doctor/queue/${row.id}/start-visit');
      expect(source).not.toContain('/registrar/queue/${row.id}/start-visit');
    }
  });

  it('does not treat queue row ids as appointment ids for legacy appointment flow', () => {
    for (const filePath of DOCTOR_PANEL_FILES) {
      const source = read(filePath);

      expect(source).not.toContain('entry.appointment_id || entry.id');
      expect(source).not.toContain('row?.appointment_id || row?.id');
      expect(source).not.toContain('row.appointment_id || row.id');
      expect(source).not.toContain('appointment.appointment_id || appointment.id');
    }
  });

  it('does not introduce BFF-lite endpoints while repairing doctor contracts', () => {
    for (const filePath of DOCTOR_PANEL_FILES) {
      const source = read(filePath);

      expect(source).not.toContain('/api/v1/ui/');
      expect(source).not.toContain('/ui/doctor');
      expect(source).not.toContain('/ui/registrar');
    }
  });

  it('renders a safe visit empty state when specialty visit tabs have no selected context', () => {
    const cardiology = read('pages/CardiologistPanelUnified.jsx');
    const dermatology = read('pages/DermatologistPanelUnified.jsx');

    expect(cardiology).toContain("activeTab === 'visit' && !selectedPatient");
    expect(cardiology).toContain('title="Выберите визит"');
    expect(cardiology).toContain("goToTab('appointments')");

    expect(dermatology).toContain("activeTab === 'visit' && !currentAppointment && !selectedPatient");
    expect(dermatology).toContain('title="Выберите визит"');
    expect(dermatology).toContain("handleTabChange('appointments')");
  });

  it('keeps the active doctor queue page action visibility backend-owned', () => {
    const source = read('pages/DoctorPanel.jsx');
    const actionBlock = extractBlock(
      source,
      'Backend-owned queue action contract',
      '</td>',
    );

    expect(source).toContain('const hasBackendQueueAction =');
    expect(source).toContain('canCallNext');
    expect(source).toContain('disabled={!canCallNext}');
    expect(actionBlock).toContain("hasBackendQueueAction(entry, 'no_show', 'can_no_show')");
    expect(actionBlock).toContain("hasBackendQueueAction(entry, 'send_to_diagnostics', 'can_send_to_diagnostics')");
    expect(actionBlock).toContain("hasBackendQueueAction(entry, 'notify_diagnostics_return', 'can_notify_diagnostics_return')");
    expect(actionBlock).toContain("hasBackendQueueAction(entry, 'restore_next', 'can_restore_next')");
    expect(actionBlock).not.toContain("entry.status === 'waiting'");
    expect(actionBlock).not.toContain("entry.status === 'called'");
    expect(actionBlock).not.toContain("entry.status === 'diagnostics'");
    expect(actionBlock).not.toContain("entry.status === 'no_show'");
  });

  it('selects call-next from backend queue contract instead of local waiting-status scan', () => {
    const source = read('hooks/useDoctorQueue.js');
    const callNextBlock = extractBlock(
      source,
      'const callNext = useCallback',
      'const markNoShow = useCallback',
    );

    expect(source).toContain('const selectNextCallEntryId =');
    expect(source).toContain('queuePayload?.next_call_entry_id');
    expect(source).toContain("hasBackendQueueAction(entry, 'call', 'can_call')");
    expect(source).toContain('canCallNext: queueControls.canCallNext');
    expect(callNextBlock).toContain('selectNextCallEntryId(currentQueue.data)');
    expect(callNextBlock).toContain('/doctor/queue/${nextCallEntryId}/call');
    expect(callNextBlock).not.toContain("entry.status === 'waiting'");
    expect(callNextBlock).not.toContain('waitingEntry');
  });
});
