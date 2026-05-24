import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const registrarPanelPath = path.resolve(__dirname, '../RegistrarPanel.jsx');

const readRegistrarPanelSource = () => fs.readFileSync(registrarPanelPath, 'utf8');

const extractSourceBlock = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('RegistrarPanel command contract', () => {
  it('uses the backend registrar record action endpoint for queue/payment/status commands', () => {
    const source = readRegistrarPanelSource();

    expect(source).toContain("api.post('/registrar/records/actions'");
    expect(source).not.toContain('/registrar/visits/${recordId}/mark-paid');
    expect(source).not.toContain('/registrar/queue/entry/${recordId}/mark-paid');
    expect(source).not.toContain('/appointments/${recordId}/mark-paid');
    expect(source).not.toContain('/registrar/visits/${realId}/complete');
    expect(source).not.toContain('/registrar/queue/${realId}/start-visit');
    expect(source).not.toContain('/online-queue/entries/${targetId}/cancel');
  });

  it('passes through registrar queue patient display fields before legacy patient fetch fallback', () => {
    const source = readRegistrarPanelSource();

    expect(source).toContain('if (apt.patient_id && !hasBackendPatientDisplayContract(apt))');
    expect(source).toContain('patient_fio: fullEntry.patient_fio ?? fullEntry.patient_name');
    expect(source).toContain('patient_birth_year: fullEntry.patient_birth_year ?? fullEntry.birth_year');
    expect(source).toContain('patient_phone: fullEntry.patient_phone ?? fullEntry.phone');
    expect(source).toContain('address: fullEntry.address ?? entry.address');
  });

  it('gates record commands through backend-provided available_actions and can flags', () => {
    const source = readRegistrarPanelSource();
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
    expect(hasBackendActionBlock).toContain("mark_paid: 'can_mark_paid'");
    expect(hasBackendActionBlock).toContain("start_visit: 'can_start_visit'");
    expect(hasBackendActionBlock).toContain("print_ticket: 'can_print_ticket'");
    expect(hasBackendActionBlock).toContain("complete: 'can_complete'");
    expect(hasBackendActionBlock).toContain("cancel: 'can_cancel'");
    expect(runActionBlock.indexOf('if (!hasBackendAction(record, action))')).toBeLessThan(
      runActionBlock.indexOf("api.post('/registrar/records/actions'"),
    );
  });

  it('does not gate command execution from record type or payment display grouping', () => {
    const source = readRegistrarPanelSource();
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
    const source = readRegistrarPanelSource();

    expect(source).toContain('sortRegistrarRowsForPresentation');
    expect(source).toContain('const sorted = sortRegistrarRowsForPresentation(entriesForTab)');
    expect(source).toContain('const filtered = sortRegistrarRowsForPresentation(appointments.filter');
    expect(source).toContain('return sortRegistrarRowsForPresentation(searched)');
    expect(source).toContain('const sortedAggregated = sortRegistrarRowsForPresentation(aggregatedPatients)');
    expect(source).toContain('return sortRegistrarRowsForPresentation(appointments)');
  });
});

