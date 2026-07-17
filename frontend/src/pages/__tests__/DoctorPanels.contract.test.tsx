import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src');

const DOCTOR_PANEL_FILES = [
  'pages/CardiologistPanelUnified.tsx',
  'pages/DentistPanelUnified.tsx',
  'pages/DermatologistPanelUnified.tsx',
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

      expect(source).toContain('payment_status: entry.payment_status ?? null');
      expect(source).toContain('payment_type: entry.payment_type');
      expect(source).toContain('queue_status: entry.queue_status ?? null');
      expect(source).toContain('canonical_status: entry.canonical_status ?? null');
      expect(source).toContain('status: entry.status ?? null');
      expect(source).toContain('available_actions: entry.available_actions || []');
      expect(source).toContain('can_mark_paid: Boolean(entry.can_mark_paid)');
      expect(source).toContain('can_start_visit: Boolean(entry.can_start_visit) && doctorQueueEntryId !== null');
      expect(source).toContain('can_print_ticket: Boolean(entry.can_print_ticket)');
      expect(source).toContain('can_complete: Boolean(entry.can_complete) && doctorQueueEntryId !== null');
      expect(source).toContain('can_cancel: Boolean(entry.can_cancel)');
      expect(source).toContain('doctor_queue_entry_id: doctorQueueEntryId');

      expect(source).not.toContain('payment_status: entry.payment_status || \'pending\'');
      expect(source).not.toContain('status: entry.status || \'waiting\'');
      expect(source).not.toContain('payment_status: row.payment_status || \'pending\'');
      expect(source).not.toContain('status: row.status || \'waiting\'');
      expect(source).not.toContain('queue_status: entry.queue_status || entry.status');
      expect(source).not.toContain('canonical_status: entry.canonical_status || entry.status');
    }
  });

  it('keeps doctor table command visibility backend-owned when rows are missing action fields', () => {
    const table = read('components/tables/EnhancedAppointmentsTable.tsx');
    const actionBlock = extractBlock(
      table,
      'const backendCanPay = getBackendActionAvailability',
      'return (',
    );

    expect(actionBlock).toContain('getBackendActionAvailability(row, \'call\', \'can_start_visit\')');
    expect(actionBlock).toContain('getBackendActionAvailability(row, \'print\', \'can_print_ticket\')');
    expect(actionBlock).toContain('getBackendActionAvailability(row, \'complete\', \'can_complete\')');
    expect(actionBlock).toContain('getBackendActionAvailability(row, \'view_emr\', \'can_view_emr\')');
    expect(actionBlock).toContain('getBackendActionAvailability(row, \'schedule_next\', \'can_schedule_next\')');
    expect(actionBlock).toContain('const canPay = !isDoctorView && backendCanPay === true');
    expect(actionBlock).toContain('const canCall = isDoctorView && backendCanCall === true');
    expect(actionBlock).toContain('const canPrint = backendCanPrint === true');
    expect(actionBlock).toContain('const canComplete = isDoctorView && backendCanComplete === true');
    expect(actionBlock).toContain('const canViewEmr = isDoctorView && backendCanViewEmr === true');
    expect(actionBlock).toContain('const canScheduleNext = isDoctorView && backendCanScheduleNext === true');
    expect(actionBlock).not.toContain('rowStatus');
    expect(actionBlock).not.toContain('rowPaymentStatus');
    expect(actionBlock).not.toContain('isDoctorView ?\n                  rowStatus');
    expect(actionBlock).not.toContain('rowPaymentStatus === \'paid\' :');
    expect(table).not.toContain('row.status === \'served\' || row.status === \'completed\'');
    expect(table).not.toContain('row.status === \'in_visit\' && row.payment_status === \'paid\'');
    expect(table).not.toContain('isDoctorView && row.status === \'done\'');
  });

  it('routes queue commands through the doctor command surface using only OnlineQueueEntry ids', () => {
    for (const filePath of DOCTOR_PANEL_FILES) {
      const source = read(filePath);

      expect(source).toContain('function resolveDoctorQueueEntryId(row)');
      expect(source).toContain('const explicitQueueEntryId = row?.doctor_queue_entry_id ?? row?.queue_entry_id ?? null;');
      expect(source).toContain('/doctor/queue/${queueEntryId}/start-visit');
      expect(source).not.toContain('recordKind === \'online_queue\' && row?.id');
      expect(source).not.toContain('/doctor/queue/${row.id}/start-visit');
      expect(source).not.toContain('completeVisit(selectedPatient.id');
      expect(source).not.toContain('const entryId = selectedPatient?.id || currentAppointment?.id');
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
    const cardiology = read('pages/CardiologistPanelUnified.tsx');
    const cardiologyVisitTab = read('components/cardiology/VisitTab.tsx');
    const dermatology = read('pages/DermatologistPanelUnified.tsx');

    // R-15: visit tab extracted to VisitTab.jsx — check both files.
    // Phase 4+: sidebar reduced — 'appointments' merged into 'patients' tab.
    // Back-compat: 'appointments' case still renders, but 'patients' is the
    // new canonical tab name.
    const cardiologySource = cardiology + '\n' + cardiologyVisitTab;
    expect(cardiologySource).toContain('activeTab === \'visit\'');
    expect(cardiologySource).toContain('cardio_visit_empty_title');
    // Must redirect to a tab that exists in the sidebar (patients or appointments alias).
    expect(
      cardiologySource.includes('goToTab(\'patients\')') ||
      cardiologySource.includes('goToTab(\'appointments\')')
    ).toBe(true);

    expect(dermatology).toContain('activeTab === \'visit\' && !currentAppointment && !selectedPatient');
    expect(dermatology).toContain('derma_panel_select_visit_title');
    expect(
      dermatology.includes('handleTabChange(\'patients\')') ||
      dermatology.includes('handleTabChange(\'appointments\')')
    ).toBe(true);
  });

  it('keeps dermatology prescription availability backend-owned', () => {
    const dermatology = read('pages/DermatologistPanelUnified.tsx');
    const prescriptionSystem = read('components/PrescriptionSystem.tsx');

    expect(dermatology).toContain('/appointments/${appointmentId}/status');
    expect(dermatology).toContain('setCanCreatePrescription(statusData.can_create_prescription === true)');
    expect(dermatology).toContain('canCreatePrescription={canCreatePrescription}');

    expect(prescriptionSystem).toContain('canCreatePrescription');
    expect(prescriptionSystem).toContain('const prescriptionEligible = canCreatePrescription === true');
    expect(prescriptionSystem).toContain('const canEdit = prescriptionEligible');
    expect(prescriptionSystem).not.toContain('from \'../constants/appointmentStatus\'');
    expect(prescriptionSystem).not.toContain('canCreatePrescription(appointment?.status');
    expect(prescriptionSystem).not.toContain('appointment?.status !== APPOINTMENT_STATUS.COMPLETED');
  });

  it('keeps the active doctor queue page action visibility backend-owned', () => {
    // UX-AUDIT-PRE: queue rendering переехал в DoctorQueuePanel.jsx
    // (UX Audit Doctor H-30). Тест обновлён, чтобы читать актуальный файл.
    // Контракт SSOT остаётся тем же: все действия gated через
    // hasBackendQueueAction(), не через status-стринги.
    const source = read('components/doctor/DoctorQueuePanel.tsx');

    expect(source).toContain('const hasBackendQueueAction =');
    // DoctorPanel.jsx по-прежнему деструктурирует canCallNext из хука очереди
    const doctorPanelSource = read('pages/DoctorPanel.tsx');
    expect(doctorPanelSource).toContain('canCallNext');

    // Текущий набор действий в очереди: call / start_visit / complete.
    // Старые действия (no_show, send_to_diagnostics, notify_diagnostics_return,
    // restore_next) убраны из UI очереди — теперь управляются через
    // useDoctorQueue hook на уровне DoctorPanel, а не на строке очереди.
    expect(source).toContain('hasBackendQueueAction(entry, \'call\', \'can_call\')');
    expect(source).toContain('hasBackendQueueAction(entry, \'start_visit\', \'can_start_visit\')');
    expect(source).toContain('hasBackendQueueAction(entry, \'complete\', \'can_complete\')');

    // SSOT-контракт: никаких status-стрингов в условиях видимости действий
    expect(source).not.toContain('entry.status === \'waiting\'');
    expect(source).not.toContain('entry.status === \'called\'');
    expect(source).not.toContain('entry.status === \'diagnostics\'');
    expect(source).not.toContain('entry.status === \'no_show\'');
    expect(source).not.toContain('entry.status === \'in_progress\'');
  });

  it('selects call-next from backend queue contract instead of local waiting-status scan', () => {
    const source = read('hooks/useDoctorQueue.ts');
    const callNextBlock = extractBlock(
      source,
      'const callNext = useCallback',
      'const markNoShow = useCallback',
    );

    expect(source).toContain('const selectNextCallEntryId =');
    expect(source).toContain('queuePayload?.next_call_entry_id');
    expect(source).toContain('hasBackendQueueAction(entry, \'call\', \'can_call\')');
    expect(source).toContain('canCallNext: response.data?.can_call_next === true');
    expect(source).toContain('canCallNext: queueControls.canCallNext');
    expect(callNextBlock).toContain('selectNextCallEntryId(currentQueue.data)');
    expect(callNextBlock).toContain('/doctor/queue/${nextCallEntryId}/call');
    expect(source).not.toContain('canCallNext: Boolean(response.data?.can_call_next ?? nextCallEntryId)');
    expect(callNextBlock).not.toContain('entry.status === \'waiting\'');
    expect(callNextBlock).not.toContain('waitingEntry');
  });
});
