/**
 * Audit 3892 round 3 — fail-first regressions for the dentist completion
 * action cluster:
 *
 *  - DENTICD-FE-001: the critical ICD-10 safety gate and the queue payload
 *    use the canonical nested diagnosis.icd10_code (backend extractor
 *    priority) instead of only the flat aliases.
 *  - DENTSYNC-FE-001: the queue completion notes fall back to the nested
 *    specialty_data.visit_protocol.recommendations when the top-level
 *    recommendation/notes are empty.
 *  - DENTDIALOG-FE-001 (action side): the standalone dental-chart dialog
 *    requires a canonical visit before opening.
 *  - DENTVISIT-FE-002 (ack contract): handleCompleteVisit reports its
 *    outcome (true = completed, false = failed, undefined = user aborted)
 *    so the visit screen can surface a persistent failure state.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import notify from '../../../services/notify';
import { queueService } from '../../../services/queue';

import { useDentistActions } from '../useDentistActions';
import type { SelectedPatient } from '../dentistContracts';

vi.mock('../../../services/notify', () => ({
  default: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../../api/client', () => ({
  apiClient: { post: vi.fn(async () => ({ status: 200 })) },
}));
vi.mock('../../../utils/tokenManager', () => ({
  default: { getAccessToken: vi.fn(() => 'test-token') },
}));
vi.mock('../../../services/queue', () => ({
  queueService: {
    startVisit: vi.fn(async () => ({ success: true, patient_id: 23, visit_id: 77, status: 'in_progress' })),
    completeVisit: vi.fn(async () => ({ success: true })),
    callNextWaiting: vi.fn(async () => ({ success: true, entry: { number: 7 } })),
  },
}));
vi.mock('../../../services/panelPrint', () => ({
  printPanelTicket: vi.fn(async () => ({ message: 'printed' })),
}));

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

type Deps = Parameters<typeof useDentistActions>[0];

const makeDeps = (overrides: Partial<Deps> = {}): Deps => ({
  tI18n: t,
  confirm: vi.fn(async () => true),
  setLoading: vi.fn(),
  selectedPatient: null,
  setSelectedPatient: vi.fn(),
  handleTabChange: vi.fn(),
  ensureCanonicalVisitId: vi.fn(async () => null),
  loadDentistryAppointments: vi.fn(async () => []),
  loadDentistVisitProtocolByVisitId: vi.fn(async () => null),
  setShowDiagnosisForm: vi.fn(),
  setShowVisitProtocol: vi.fn(),
  setShowPhotoArchive: vi.fn(),
  setShowProtocolTemplates: vi.fn(),
  setShowReports: vi.fn(),
  setShowDentalChart: vi.fn(),
  setShowTreatmentPlanner: vi.fn(),
  setDentalChartData: vi.fn(),
  setProtocolTemplateDraft: vi.fn(),
  ...overrides,
});

const patientWith = (extra: Partial<SelectedPatient>): SelectedPatient =>
  ({ doctor_queue_entry_id: 99, patient_name: 'P', ...extra }) as SelectedPatient;

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useDentistActions canonical completion (audit 3892 round 3)', () => {
  it('DENTICD-FE-001: a nested-only critical ICD code selects the danger confirmation', async () => {
    const confirm = vi.fn(async (_options: Record<string, unknown>) => false);
    const deps = makeDeps({
      confirm,
      selectedPatient: patientWith({ patient_id: 42 }),
    });
    const { result } = renderHook(() => useDentistActions(deps));

    await result.current.handleCompleteVisit({
      diagnosis: { main: 'apical periodontitis', icd10_code: 'K04.7' },
    });

    const options = confirm.mock.calls[0][0] as Record<string, unknown>;
    expect(options.intent).toBe('danger');
    expect(queueService.completeVisit).not.toHaveBeenCalled();
  });

  it('DENTICD-FE-001: the nested code wins over a conflicting non-critical flat alias', async () => {
    const confirm = vi.fn(async (_options: Record<string, unknown>) => true);
    const deps = makeDeps({
      confirm,
      selectedPatient: patientWith({ patient_id: 42 }),
    });
    const { result } = renderHook(() => useDentistActions(deps));

    await result.current.handleCompleteVisit({
      diagnosis: { main: 'jaw bone disease', icd10_code: 'K10.2' },
      icd10_code: 'K02.1',
    });

    expect((confirm.mock.calls[0][0] as Record<string, unknown>).intent).toBe('danger');
    await waitFor(() => expect(queueService.completeVisit).toHaveBeenCalledWith(99, expect.objectContaining({
      icd10: 'K10.2',
    })));
  });

  it('DENTICD-FE-001 (control): a non-critical nested code keeps the primary confirmation', async () => {
    const confirm = vi.fn(async (_options: Record<string, unknown>) => false);
    const deps = makeDeps({
      confirm,
      selectedPatient: patientWith({ patient_id: 42 }),
    });
    const { result } = renderHook(() => useDentistActions(deps));

    await result.current.handleCompleteVisit({
      diagnosis: { main: 'dental caries', icd10_code: 'K02.1' },
    });

    expect((confirm.mock.calls[0][0] as Record<string, unknown>).intent).toBe('primary');
  });

  it('DENTICD-FE-001 (control): flat-only legacy codes keep their historical behavior', async () => {
    const confirm = vi.fn(async (_options: Record<string, unknown>) => false);
    const deps = makeDeps({
      confirm,
      selectedPatient: patientWith({ patient_id: 42 }),
    });
    const { result } = renderHook(() => useDentistActions(deps));

    await result.current.handleCompleteVisit({ icd10_code: 'K04.7' });

    expect((confirm.mock.calls[0][0] as Record<string, unknown>).intent).toBe('danger');
  });

  it('DENTSYNC-FE-001: nested visit-protocol recommendations reach the queue notes when top-level fields are empty', async () => {
    const deps = makeDeps({
      selectedPatient: patientWith({ patient_id: 42 }),
    });
    const { result } = renderHook(() => useDentistActions(deps));

    await result.current.handleCompleteVisit({
      specialty_data: {
        visit_protocol: { recommendations: 'review in one week' },
      },
    });

    await waitFor(() => expect(queueService.completeVisit).toHaveBeenCalledWith(99, expect.objectContaining({
      notes: 'review in one week',
    })));
  });

  it('DENTSYNC-FE-001 (control): a top-level recommendation still takes precedence over the nested one', async () => {
    const deps = makeDeps({
      selectedPatient: patientWith({ patient_id: 42 }),
    });
    const { result } = renderHook(() => useDentistActions(deps));

    await result.current.handleCompleteVisit({
      recommendations: 'top-level recommendation',
      specialty_data: {
        visit_protocol: { recommendations: 'nested recommendation' },
      },
    });

    await waitFor(() => expect(queueService.completeVisit).toHaveBeenCalledWith(99, expect.objectContaining({
      notes: 'top-level recommendation',
    })));
  });

  it('DENTVISIT-FE-002 (ack): a confirmed completion reports true', async () => {
    const deps = makeDeps({ selectedPatient: patientWith({ patient_id: 42 }) });
    const { result } = renderHook(() => useDentistActions(deps));

    const ack = await result.current.handleCompleteVisit({
      diagnosis: 'stable diagnosis',
      icd10_code: 'K02.1',
    });
    expect(ack).toBe(true);
  });

  it('DENTVISIT-FE-002 (ack): a server-rejected completion reports false', async () => {
    vi.mocked(queueService.completeVisit).mockResolvedValueOnce({ success: false } as never);
    const deps = makeDeps({ selectedPatient: patientWith({ patient_id: 42 }) });
    const { result } = renderHook(() => useDentistActions(deps));

    const ack = await result.current.handleCompleteVisit({
      diagnosis: 'stable diagnosis',
      icd10_code: 'K02.1',
    });
    expect(ack).toBe(false);
    expect(notify.error).toHaveBeenCalled();
    expect(deps.handleTabChange).not.toHaveBeenCalledWith('queue');
  });

  it('DENTVISIT-FE-002 (ack): a user-cancelled confirmation reports an abort, not a failure', async () => {
    const confirm = vi.fn(async (_options: Record<string, unknown>) => false);
    const deps = makeDeps({
      confirm,
      selectedPatient: patientWith({ patient_id: 42 }),
    });
    const { result } = renderHook(() => useDentistActions(deps));

    const ack = await result.current.handleCompleteVisit({
      diagnosis: 'stable diagnosis',
      icd10_code: 'K02.1',
    });
    expect(ack).toBeUndefined();
    expect(notify.error).not.toHaveBeenCalled();
  });

  it('DENTDIALOG-FE-001: the dental chart refuses to open without a canonical visit', async () => {
    const deps = makeDeps({
      selectedPatient: patientWith({ patient_id: 23 }),
      ensureCanonicalVisitId: vi.fn(async () => null),
    });
    const { result } = renderHook(() => useDentistActions(deps));

    await result.current.handleDentalChart({ id: 23, patient_id: 23 });

    expect(notify.error).toHaveBeenCalledWith('dental.dental_chart_needs_visit_id');
    expect(deps.setShowDentalChart).not.toHaveBeenCalled();
  });

  it('DENTDIALOG-FE-001: the dental chart resolves the canonical visit before opening', async () => {
    const deps = makeDeps({
      selectedPatient: patientWith({ patient_id: 23 }),
      ensureCanonicalVisitId: vi.fn(async () => 55),
    });
    const { result } = renderHook(() => useDentistActions(deps));

    await result.current.handleDentalChart({ id: 23, patient_id: 23, patient_name: 'SYNTHETIC Patient' });

    expect(deps.setShowDentalChart).toHaveBeenCalledWith(true);
    expect(deps.setSelectedPatient).toHaveBeenCalledWith(expect.objectContaining({
      patient_id: 23,
      visit_id: 55,
    }));
    expect(notify.error).not.toHaveBeenCalled();
  });
});
