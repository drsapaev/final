import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const registrarPanelPath = path.resolve(__dirname, '../RegistrarPanel.jsx');
// Decomp step 1: helpers extracted to ./registrar/registrarHelpers.js.
// Decomp step 2: hotkeys extracted to ./registrar/useRegistrarHotkeys.js.
// Decomp step 3: reschedule helpers extracted to ./registrar/useRegistrarReschedule.js.
// Decomp step 4: data-loading functions extracted to ./registrar/useRegistrarData.js.
// Decomp step 5: record action handlers extracted to ./registrar/useRegistrarActions.js.
// Contract tests must read all files because they verify that certain
// functions exist in the registrar panel source tree (not necessarily
// in the orchestrator file itself).
const registrarHelpersPath = path.resolve(__dirname, '../registrar/registrarHelpers.js');
const useRegistrarHotkeysPath = path.resolve(__dirname, '../registrar/useRegistrarHotkeys.js');
const useRegistrarReschedulePath = path.resolve(__dirname, '../registrar/useRegistrarReschedule.js');
const useRegistrarDataPath = path.resolve(__dirname, '../registrar/useRegistrarData.js');
const useRegistrarActionsPath = path.resolve(__dirname, '../registrar/useRegistrarActions.js');

const readRegistrarPanelSource = () => fs.readFileSync(registrarPanelPath, 'utf8');
const readRegistrarHelpersSource = () => fs.readFileSync(registrarHelpersPath, 'utf8');
const readRegistrarSourceTree = () => [
  readRegistrarPanelSource(),
  '// ─── registrarHelpers.js ───',
  readRegistrarHelpersSource(),
  '// ─── useRegistrarHotkeys.js ───',
  fs.readFileSync(useRegistrarHotkeysPath, 'utf8'),
  '// ─── useRegistrarReschedule.js ───',
  fs.readFileSync(useRegistrarReschedulePath, 'utf8'),
  '// ─── useRegistrarData.js ───',
  fs.readFileSync(useRegistrarDataPath, 'utf8'),
  '// ─── useRegistrarActions.js ───',
  fs.readFileSync(useRegistrarActionsPath, 'utf8'),
].join('\n\n');

const extractSourceBlock = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
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
      'const enrichAppointmentsWithPatientData = useCallback(async (appointments) => {',
      'return enrichedAppointments;',
    );

    expect(source).toContain('if (apt.patient_id && (!hasBackendPatientDisplayContract(apt) || !hasBackendPatientGenderContract(apt)))');
    expect(source).toContain('patient_fio: fullEntry.patient_fio ?? fullEntry.patient_name');
    expect(source).toContain('patient_birth_year: fullEntry.patient_birth_year ?? fullEntry.birth_year');
    expect(source).toContain('patient_phone: fullEntry.patient_phone ?? fullEntry.phone');
    expect(source).toContain('address: fullEntry.address ?? entry.address');
    expect(source).toContain('const gender = normalizePatientGender(record);');
    expect(source).toContain('String(gender).trim() !== \'\'');
    expect(enrichmentBlock).toContain('!hasBackendPatientGenderContract(apt)');
    expect(enrichmentBlock).toContain('patient_gender: patientGender');
    expect(enrichmentBlock.indexOf('!hasBackendPatientDisplayContract(apt)')).toBeLessThan(
      enrichmentBlock.indexOf('fetchPatientData(apt.patient_id)'),
    );
  });

  it('keeps Registrar table view separate from edit mode', () => {
    const source = readRegistrarSourceTree();

    expect(source).toContain('const openRecordPreview = useCallback((row) => {');
    expect(source).toContain('const openRecordEditor = useCallback((row) => {');
    expect(source).toContain('case \'view\':');
    expect(source).toContain('openRecordPreview(row);');
    expect(source).toContain('case \'edit\':');
    expect(source).toContain('openRecordEditor(row);');
  });

  it('allows edit mode for aggregate all-departments rows while keeping preview separate', () => {
    const source = readRegistrarSourceTree();
    const editBlock = extractSourceBlock(
      source,
      'const openRecordEditor = useCallback((row) => {',
      'const handleContextMenuAction = useCallback(async (action, row) => {',
    );

    expect(source).toContain('const isMultiRecordAggregateRow = (row) => (');
    expect(source).toContain('hasMultipleRecordRefs(row?.grouped_record_refs)');
    expect(editBlock).toContain('if (isMultiRecordAggregateRow(row))');
    expect(editBlock).toContain('Opening edit wizard for aggregate all-departments row');
    expect(editBlock).not.toContain('openRecordPreview(row);');
    expect(editBlock).not.toContain('notify.warning');
    expect(editBlock).toContain('setShowWizard(true);');
  });

  it('restores post-wizard payment or ticket handoff for creates and paid edit deltas', () => {
    const source = readRegistrarSourceTree();

    expect(source).toContain('const buildPostWizardPaymentRow = (wizardResult) => {');
    expect(source).toContain('const normalizeWizardQueueAssignment = (assignment, visitId = null) => {');
    expect(source).toContain('const resolveWizardQueueEntryId = (assignment) => {');
    expect(source).toContain('if (hasQueueIdentityValue(assignment.queue_id)) return null;');
    expect(source).toContain('if (Array.isArray(queueNumbers))');
    expect(source).toContain('queue_entry_id: queueEntryId');
    expect(source).not.toContain('queue_entry_id: assignment.queue_entry_id ?? assignment.queue_id ?? assignment.id ?? null');
    expect(source).toContain('number: queueNumber');
    expect(source).toContain('grouped_record_refs: visitIds.map');
    expect(source).toContain('queue_number: firstQueueNumber?.queue_number ?? null');
    expect(source).toContain('print_tickets: printTickets');
    expect(source).toContain('const postWizardPaymentRow = (!wasEditMode || Number(wizardData?.total_amount || 0) > 0)');
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
      'const fetchPatientData = useCallback(async (patientId) => {',
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
      'const filterServicesByDepartment = useCallback((appointment, departmentKey) => {',
      'const filteredAppointments = useMemo(() => {',
    );

    expect(source).toContain('service_details: Array.isArray(fullEntry.service_details) ? fullEntry.service_details : []');
    expect(filterBlock).toContain('const filterByBackendDepartment = (appointmentServices) => {');
    expect(filterBlock).toContain('serviceMeta?.department_key ?? serviceMeta?.departmentKey');
    expect(filterBlock.indexOf('const backendFilteredServices = filterByBackendDepartment(appointment.services || [])')).toBeLessThan(
      filterBlock.indexOf('const departmentCodePrefixes = {'),
    );
    expect(filterBlock.indexOf('const backendFilteredServices = filterByBackendDepartment(appointmentServices)')).toBeLessThan(
      filterBlock.indexOf('const serviceToCodeMap = new Map()'),
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
      'const hasBackendAction = (record, action) => {',
      'const getRegistrarActionForStatus = (status) => {',
    );
    const runActionBlock = extractSourceBlock(
      source,
      'const runRegistrarRecordAction = useCallback(async (record, action, payload = {}) => {',
      'const handleStartVisit = useCallback(async (appointment) => {',
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
      'const hasBackendAction = (record, action) => {',
      'const getRegistrarActionForStatus = (status) => {',
    );
    const runActionBlock = extractSourceBlock(
      source,
      'const runRegistrarRecordAction = useCallback(async (record, action, payload = {}) => {',
      'const handleStartVisit = useCallback(async (appointment) => {',
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
      'const resolveRescheduleVisitId = useCallback((appointmentRow) => {',
      'const removeRescheduledAppointmentFromView = useCallback',
    );

    expect(source).toContain('appointment_id: fullEntry.appointment_id || entry.appointment_id || null');
    expect(source).not.toContain('appointment_id: fullEntry.appointment_id || entry.appointment_id || entryId');
    expect(resolverBlock).toContain('appointmentRow?.visit_ids?.[0]');
    expect(resolverBlock).toContain('appointmentRow?.visit_id');
    expect(resolverBlock).toContain('appointmentRow?.visitId');
    expect(resolverBlock).not.toContain('appointment_id');
    expect(resolverBlock).not.toContain('appointment_ids');
    expect(resolverBlock).not.toContain('appointmentRow?.id');
    expect(source).toContain("tI18n('registrar.no_visit_for_postpone')");
  });
});

