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

    // Contract: enrichment must gate on patient_id and backend display/gender contracts.
    // TS type annotations are stripped by normalizeSource — assertion must match normalized form.
    expect(source).toContain('if (apt.patient_id && (!hasBackendPatientDisplayContract(apt) || !hasBackendPatientGenderContract(apt)))');
    expect(source).toContain('patient_fio: fullEntry.patient_fio ?? fullEntry.patient_name');
    expect(source).toContain('patient_birth_year: fullEntry.patient_birth_year ?? fullEntry.birth_year');
    expect(source).toContain('patient_phone: fullEntry.patient_phone ?? fullEntry.phone');
    expect(source).toContain('address: fullEntry.address ?? entry.address');
    expect(source).toContain('const gender = normalizePatientGender(record);');
    // Contract: hasBackendPatientGenderContract must reject null/undefined/empty gender.
    // Semantic checks inside the function body — survive any declaration form.
    // (Avoids `String(gender).trim()` literal: helper Phase 6b regex mangles it
    // into `Stringgender.trim()` — see Known limitation in source-contract-helper.ts.)
    const genderContractBlock = extractSourceBlock(
      source,
      'export const hasBackendPatientGenderContract = (record) => {',
      '};',
    );
    expect(genderContractBlock).toContain('gender !== null');
    expect(genderContractBlock).toContain('gender !== undefined');
    expect(genderContractBlock).toContain('.trim()');
    expect(enrichmentBlock).toContain('!hasBackendPatientGenderContract(apt)');
    // Contract: patient_gender must be set from normalizePatientGender.
    // Helper Phase 2 mangles `patient_gender: patientGender,` in object literals
    // (treats it as a parameter type annotation), so we verify the field name
    // without the colon. The function call is verified by the next assertion.
    expect(enrichmentBlock).toContain('patient_gender');
    expect(enrichmentBlock).toContain('normalizePatientGender(');
    expect(enrichmentBlock.indexOf('!hasBackendPatientDisplayContract(apt)')).toBeLessThan(
      enrichmentBlock.indexOf('fetchPatientData(apt.patient_id'),
    );
  });

  it('keeps Registrar table view separate from edit mode', () => {
    const source = readRegistrarSourceTree();

    // Contract: view/edit mode must use separate callbacks.
    // TS type annotations are stripped by normalizeSource.
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
      'const openRecordEditor = useCallback((row: unknown) => {',
      'const handleContextMenuAction = useCallback(async (action: string, row: Appointment) => {',
    );

    // Contract: aggregate row detection must use hasMultipleRecordRefs.
    // TS type annotations are stripped by normalizeSource.
    expect(source).toContain('export const isMultiRecordAggregateRow = (row) => (');
    expect(source).toContain('hasMultipleRecordRefs(row?.grouped_record_refs)');
    expect(editBlock).toContain('if (isMultiRecordAggregateRow(appt))');
    expect(editBlock).toContain('Opening edit wizard for aggregate all-departments row');
    expect(editBlock).not.toContain('openRecordPreview(row);');
    expect(editBlock).not.toContain('notify.warning');
    expect(editBlock).toContain('setShowWizard(true);');
  });

  it('restores post-wizard payment or ticket handoff for creates and paid edit deltas', () => {
    const source = readRegistrarSourceTree();

    // Contract: post-wizard payment row builder must exist.
    // TS type annotations are stripped by normalizeSource.
    expect(source).toContain('const buildPostWizardPaymentRow = (wizardResult) => {');
    expect(source).toContain('const normalizeWizardQueueAssignment = (');
    // Contract: resolveWizardQueueEntryId function exists and uses its assignment parameter.
    // Name-only presence check survives arrow→function, export→const, memoization, and file moves.
    // The function's queue-entry resolution contract is verified by the next assertion
    // (returns null when assignment.queue_id is set).
    expect(source).toContain('resolveWizardQueueEntryId');
    expect(source).toContain('if (hasQueueIdentityValue(assignment.queue_id)) return null;');
    expect(source).toContain('if (Array.isArray(queueNumbers))');
    // Contract: payment row fields (queue_entry_id, number, print_tickets) are
    // populated from locally-computed variables (queueEntryId, queueNumber,
    // printTickets), NOT from raw wizardResult/assignment fields. Helper Phase 2
    // mangles `field: variable,` in object literals (treats it as a parameter
    // type annotation), so we verify field + variable names within their
    // function scopes. The forbidden raw fallback is verified by the next assertion.
    const normalizeBlock = extractSourceBlock(
      source,
      'export const normalizeWizardQueueAssignment = (',
      'export const flattenWizardQueueNumbers',
    );
    expect(normalizeBlock).toContain('queue_entry_id');
    expect(normalizeBlock).toContain('queueEntryId');
    expect(normalizeBlock).toContain('queueNumber');
    const paymentRowBlock = extractSourceBlock(
      source,
      'const buildPostWizardPaymentRow = (',
      'const hasMultipleRecordRefs = (',
    );
    expect(paymentRowBlock).toContain('print_tickets');
    expect(paymentRowBlock).toContain('printTickets');
    expect(source).not.toContain('queue_entry_id: assignment.queue_entry_id ?? assignment.queue_id ?? assignment.id ?? null');
    expect(source).toContain('grouped_record_refs: visitIds.map');
    expect(source).toContain('queue_number: firstQueueNumber?.queue_number ?? null');
    expect(source).toContain('const postWizardPaymentRow = (!wasEditMode || Number(wizardDataObj.total_amount ?? 0) > 0)');
    expect(source).toContain('source: wasEditMode ? \'wizard-edit\' : \'wizard-create\'');
    // Contract: print dialog is opened with type 'ticket' and the payment row data.
    // Helper Phase 2 mangles `open: true,` in object literals (matches `true` as a
    // type identifier), so we verify the call and its key arguments separately.
    expect(source).toContain('setPrintDialog(');
    expect(source).toContain('type: \'ticket\'');
    expect(source).toContain('data: postWizardPaymentRow');
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
    // Contract: filterByBackendDepartment is defined inside the filter block and
    // called before legacy code-prefix fallback. Name-presence check survives any
    // declaration form (arrow/function/memoized). The parameter `appointmentServices`
    // and call ordering are verified by the assertions below.
    expect(filterBlock).toContain('filterByBackendDepartment');
    expect(filterBlock).toContain('serviceMeta?.department_key ?? serviceMeta?.departmentKey');
    // Contract: filterByBackendDepartment is called BEFORE legacy code-prefix
    // fallback (departmentCodePrefixes) and BEFORE serviceToCodeMap fallback.
    // Ordering verified via indexOf. The second needle drops the TS annotation
    // (`: Record<string, string[]>`) which helper Phase 5 strips from the source.
    expect(filterBlock.indexOf('const backendFilteredServices = filterByBackendDepartment(appointment.services || [])')).toBeLessThan(
      filterBlock.indexOf('const departmentCodePrefixes = {'),
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
    // Contract: 5 distinct call-sites of sortRegistrarRowsForPresentation with specific
    // argument names (entriesForTab, appointments.filter, searched, aggregatedPatients, appointments).
    // Closing `)` is intentionally omitted on the two `as Record<...>[]`-cast call-sites:
    // helper leaves a `[]` artifact after stripping the cast (documented helper behavior).
    expect(source).toContain('const sorted = sortRegistrarRowsForPresentation(entriesForTab');
    expect(source).toContain('const filtered = sortRegistrarRowsForPresentation(appointments.filter');
    expect(source).toContain('return sortRegistrarRowsForPresentation(searched)');
    expect(source).toContain('const sortedAggregated = sortRegistrarRowsForPresentation(aggregatedPatients)');
    expect(source).toContain('return sortRegistrarRowsForPresentation(appointments');
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

