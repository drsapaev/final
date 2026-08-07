import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { normalizeSource } from '../../test/contracts/source-contract-helper';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const registrarPanelPath = path.resolve(__dirname, '../RegistrarPanel.tsx');
// Decomp step 1: helpers extracted to ./registrar/registrarHelpers.js.
// Decomp step 2: hotkeys extracted to ./registrar/useRegistrarHotkeys.js.
// Decomp step 3: reschedule helpers extracted to ./registrar/useRegistrarReschedule.js.
// Decomp step 4: data-loading functions extracted to ./registrar/useRegistrarData.js.
// Decomp step 5: record action handlers extracted to ./registrar/useRegistrarActions.js.
// Contract tests must read all files because they verify that certain
// functions exist in the registrar panel source tree (not necessarily
// in the orchestrator file itself).
const registrarHelpersPath = path.resolve(__dirname, '../registrar/registrarHelpers.ts');
const useRegistrarHotkeysPath = path.resolve(__dirname, '../registrar/useRegistrarHotkeys.ts');
const useRegistrarReschedulePath = path.resolve(__dirname, '../registrar/useRegistrarReschedule.ts');
const useRegistrarDataPath = path.resolve(__dirname, '../registrar/useRegistrarData.ts');
const useRegistrarActionsPath = path.resolve(__dirname, '../registrar/useRegistrarActions.ts');

const readRegistrarPanelSource = () => normalizeSource(fs.readFileSync(registrarPanelPath, 'utf8'));
const readRegistrarHelpersSource = () => normalizeSource(fs.readFileSync(registrarHelpersPath, 'utf8'));
const readRegistrarSourceTree = () => [
  readRegistrarPanelSource(),
  '// ─── registrarHelpers.js ───',
  readRegistrarHelpersSource(),
  '// ─── useRegistrarHotkeys.js ───',
  normalizeSource(fs.readFileSync(useRegistrarHotkeysPath, 'utf8')),
  '// ─── useRegistrarReschedule.js ───',
  normalizeSource(fs.readFileSync(useRegistrarReschedulePath, 'utf8')),
  '// ─── useRegistrarData.js ───',
  normalizeSource(fs.readFileSync(useRegistrarDataPath, 'utf8')),
  '// ─── useRegistrarActions.js ───',
  normalizeSource(fs.readFileSync(useRegistrarActionsPath, 'utf8')),
].join('\n\n');

const extractSourceBlock = (source: string, startMarker: string, endMarker: string) => {
  const start = source.indexOf(normalizeSource(startMarker));
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(normalizeSource(endMarker), start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('RegistrarPanel command contract', () => {
  it('uses the backend registrar record action endpoint for queue/payment/status commands', () => {
    const source = readRegistrarSourceTree();

    expect(source).toContain('api.post(\'/registrar/records/actions\'');
    expect(source).not.toContain('/registrar/visits/${recordId}/mark-paid');
    expect(source).not.toContain('/registrar/queue/entry/${recordId}/mark-paid');
    expect(source).not.toContain('/appointments/${recordId}/mark-paid');
    expect(source).not.toContain('/registrar/visits/${realId}/complete');
    expect(source).not.toContain('/registrar/queue/${realId}/start-visit');
    expect(source).not.toContain('/online-queue/entries/${targetId}/cancel');
  });

  it('passes through registrar queue patient display fields before legacy patient fetch fallback', () => {
    const source = readRegistrarSourceTree();
    // Decomp 4: enrichAppointmentsWithPatientData moved to useRegistrarData.js.
    // End marker changed from 'const loadAppointments' (now in different file)
    // to 'return enrichedAppointments;' (last line of the function in the hook).
    const enrichmentBlock = extractSourceBlock(
      source,
      'const enrichAppointmentsWithPatientData = useCallback(async (appointments: Record<string, unknown>[]) => {',
      'return enrichedAppointments;',
    );

    expect(source).toContain('if (apt.patient_id as string | number && (!hasBackendPatientDisplayContract(apt) || !hasBackendPatientGenderContract(apt)))');
    expect(source).toContain('patient_fio: fullEntry.patient_fio ?? fullEntry.patient_name');
    expect(source).toContain('patient_birth_year: fullEntry.patient_birth_year ?? fullEntry.birth_year');
    expect(source).toContain('patient_phone: fullEntry.patient_phone ?? fullEntry.phone');
    expect(source).toContain('address: fullEntry.address ?? entry.address');
    expect(source).toContain('const gender = normalizePatientGender(record);');
    expect(source).toContain('String(gender).trim() !== \'\'');
    expect(enrichmentBlock).toContain('!hasBackendPatientGenderContract(apt)');
    expect(enrichmentBlock).toContain('patient_gender: patientGender');
    expect(enrichmentBlock.indexOf('!hasBackendPatientDisplayContract(apt)')).toBeLessThan(
      enrichmentBlock.indexOf('fetchPatientData(apt.patient_id as string | number)'),
    );
  });

  it('keeps Registrar table view separate from edit mode', () => {
    const source = readRegistrarSourceTree();

    expect(source).toContain('const openRecordPreview = useCallback((row: unknown) => {');
    expect(source).toContain('const openRecordEditor = useCallback((row: unknown) => {');
    expect(source).toContain('case \'view\':');
    expect(source).toContain('openRecordPreview(row);');
    expect(source).toContain('case \'edit\':');
    expect(source).toContain('openRecordEditor(row);');
  });

  it('allows edit mode for aggregate all-departments rows while keeping preview separate', () => {
    const source = readRegistrarSourceTree();
    const editBlock = extractSourceBlock(
      source,
      'const openRecordEditor = useCallback((row: unknown) => {',
      'const handleContextMenuAction = useCallback(async (action: string, row: Appointment) => {',
    );

    expect(source).toContain('export const isMultiRecordAggregateRow = (row: Record<string, unknown>) => (');
    expect(source).toContain('hasMultipleRecordRefs(row?.grouped_record_refs)');
    expect(editBlock).toContain('if (isMultiRecordAggregateRow(appt))');
    expect(editBlock).toContain('Opening edit wizard for aggregate all-departments row');
    expect(editBlock).not.toContain('openRecordPreview(row);');
    expect(editBlock).not.toContain('notify.warning');
    expect(editBlock).toContain('setShowWizard(true);');
  });

  it('restores post-wizard payment or ticket handoff for creates and paid edit deltas', () => {
    const source = readRegistrarSourceTree();

    expect(source).toContain('const buildPostWizardPaymentRow = (wizardResult: Record<string, unknown> | null | undefined) => {');
    expect(source).toContain('const normalizeWizardQueueAssignment = (');
    expect(source).toContain('const resolveWizardQueueEntryId = (assignment: Record<string, unknown> | null | undefined) => {');
    expect(source).toContain('if (hasQueueIdentityValue(assignment.queue_id)) return null;');
    expect(source).toContain('if (Array.isArray(queueNumbers))');
    expect(source).toContain('queue_entry_id: queueEntryId');
    expect(source).not.toContain('queue_entry_id: assignment.queue_entry_id ?? assignment.queue_id ?? assignment.id ?? null');
    expect(source).toContain('number: queueNumber');
    expect(source).toContain('grouped_record_refs: visitIds.map');
    expect(source).toContain('queue_number: firstQueueNumber?.queue_number ?? null');
    expect(source).toContain('print_tickets: printTickets');
    expect(source).toContain('const postWizardPaymentRow = (!wasEditMode || Number(wizardDataObj.total_amount ?? 0) > 0)');
    expect(source).toContain('source: wasEditMode ? \'wizard-edit\' : \'wizard-create\'');
    expect(source).toContain('setPrintDialog({ open: true, type: \'ticket\', data: postWizardPaymentRow });');
  });

  it('loads Registrar metadata departments through one registrar endpoint', () => {
    const source = readRegistrarSourceTree();

    expect(source).toContain('api.get(\'/registrar/departments?active_only=true\')');
    expect(source).not.toContain('/api/v1/departments/active');
    expect(source).not.toContain('const loadDynamicDepartments = useCallback');
  });

  it('does not fetch unused queue settings in the Registrar metadata bundle', () => {
    const source = readRegistrarSourceTree();
    const loadIntegratedDataBlock = extractSourceBlock(
      source,
      'const loadIntegratedData = useCallback(async () => {',
      'const fetchPatientData = useCallback(async (patientId: number | string) => {',
    );

    expect(loadIntegratedDataBlock).toContain('api.get(\'/registrar/doctors\')');
    expect(loadIntegratedDataBlock).toContain('api.get(\'/registrar/services\')');
    expect(loadIntegratedDataBlock).toContain('api.get(\'/registrar/departments?active_only=true\')');
    expect(loadIntegratedDataBlock).not.toContain('api.get(\'/registrar/queue-settings\')');
    expect(loadIntegratedDataBlock).not.toContain('queueResult');
    expect(loadIntegratedDataBlock).not.toContain('queueRes');
  });

  it('filters displayed services by backend department metadata before legacy code prefixes', () => {
    const source = readRegistrarSourceTree();
    const filterBlock = extractSourceBlock(
      source,
      'const filterServicesByDepartment = useCallback((appointment: Appointment, departmentKey: string | null) => {',
      'const filteredAppointments = useMemo(() => {',
    );

    expect(source).toContain('service_details: Array.isArray(fullEntry.service_details) ? fullEntry.service_details : []');
    expect(filterBlock).toContain('const filterByBackendDepartment = (appointmentServices: unknown[]): unknown[] | null => {');
    expect(filterBlock).toContain('serviceMeta?.department_key ?? serviceMeta?.departmentKey');
    expect(filterBlock.indexOf('const backendFilteredServices = filterByBackendDepartment(appointment.services || [])')).toBeLessThan(
      filterBlock.indexOf('const departmentCodePrefixes: Record<string, string[]> = {'),
    );
    expect(filterBlock.indexOf('const backendFilteredServices = filterByBackendDepartment(appointmentServices)')).toBeLessThan(
      filterBlock.indexOf('const serviceToCodeMap = new Map'),
    );
  });

  it('does not add a BFF-lite registrar workbench endpoint', () => {
    const source = readRegistrarSourceTree();

    expect(source).not.toContain('/api/v1/ui/');
    expect(source).not.toContain('/ui/registrar/workbench');
  });

  it('gates record commands through backend-provided available_actions and can flags', () => {
    const source = readRegistrarSourceTree();
    const hasBackendActionBlock = extractSourceBlock(
      source,
      'const hasBackendAction = (record: RegistrarRecordLike | null | undefined, action: unknown): boolean => {',
      'const getRegistrarActionForStatus = (status: unknown): string | null => {',
    );
    const runActionBlock = extractSourceBlock(
      source,
      'const runRegistrarRecordAction = useCallback(async (record: Record<string, unknown>, action: string, payload: Record<string, unknown> = {}) => {',
      'const handleStartVisit = useCallback(async (appointment: Record<string, unknown>) => {',
    );

    expect(hasBackendActionBlock).toContain('record.available_actions');
    expect(hasBackendActionBlock).toContain('mark_paid: \'can_mark_paid\'');
    expect(hasBackendActionBlock).toContain('start_visit: \'can_start_visit\'');
    expect(hasBackendActionBlock).toContain('print_ticket: \'can_print_ticket\'');
    expect(hasBackendActionBlock).toContain('complete: \'can_complete\'');
    expect(hasBackendActionBlock).toContain('cancel: \'can_cancel\'');
    expect(runActionBlock.indexOf('if (!hasBackendAction(record, action))')).toBeLessThan(
      runActionBlock.indexOf('api.post(\'/registrar/records/actions\''),
    );
  });

  it('does not gate command execution from record type or payment display grouping', () => {
    const source = readRegistrarSourceTree();
    const hasBackendActionBlock = extractSourceBlock(
      source,
      'const hasBackendAction = (record: RegistrarRecordLike | null | undefined, action: unknown): boolean => {',
      'const getRegistrarActionForStatus = (status: unknown): string | null => {',
    );
    const runActionBlock = extractSourceBlock(
      source,
      'const runRegistrarRecordAction = useCallback(async (record: Record<string, unknown>, action: string, payload: Record<string, unknown> = {}) => {',
      'const handleStartVisit = useCallback(async (appointment: Record<string, unknown>) => {',
    );
    const forbiddenDecisionInputs = [
      'record_type',
      'payment_status',
      'payment_type',
      'mixed_payment',
      'pending_payment',
      'approval_pending',
    ];

    forbiddenDecisionInputs.forEach((input) => {
      expect(hasBackendActionBlock).not.toContain(input);
      expect(runActionBlock).not.toContain(input);
    });
  });

  it('uses presentation-only sorting from backend queue_time facts', () => {
    const source = readRegistrarSourceTree();

    expect(source).toContain('sortRegistrarRowsForPresentation');
    expect(source).toContain('const sorted = sortRegistrarRowsForPresentation(entriesForTab)');
    expect(source).toContain('const filtered = sortRegistrarRowsForPresentation(appointments.filter');
    expect(source).toContain('return sortRegistrarRowsForPresentation(searched)');
    expect(source).toContain('const sortedAggregated = sortRegistrarRowsForPresentation(aggregatedPatients)');
    expect(source).toContain('return sortRegistrarRowsForPresentation(appointments)');
  });

  it('does not use appointment or queue ids as visit ids for reschedule commands', () => {
    const source = readRegistrarSourceTree();
    const resolverBlock = extractSourceBlock(
      source,
      'const resolveRescheduleVisitId = useCallback((appointmentRow: Record<string, unknown>) => {',
      'const removeRescheduledAppointmentFromView = useCallback',
    );

    expect(source).toContain('appointment_id: fullEntry.appointment_id || entry.appointment_id || null');
    expect(source).not.toContain('appointment_id: fullEntry.appointment_id || entry.appointment_id || entryId');
    expect(resolverBlock).toContain('visitIds?.[0]');
    expect(resolverBlock).toContain('appointmentRow?.visit_id');
    expect(resolverBlock).toContain('appointmentRow?.visitId');
    expect(resolverBlock).not.toContain('appointment_id');
    expect(resolverBlock).not.toContain('appointment_ids');
    expect(resolverBlock).not.toContain('appointmentRow?.id');
    expect(source).toContain("tI18n('registrar.no_visit_for_postpone')");
  });
});

