/**
 * PR-UI-15-5 unit contract: useDentistActions — verbatim extraction of the
 * DentistPanelUnified business-action handler slice (registrar/cashier
 * decomposition precedent). Pins:
 *  - patient field normalization (resolvePatientId / resolvePatientName)
 *  - queue→visit routing guards (handlePatientSelect no-visit fallback)
 *  - C-3 critical ICD-10 prefix gate (K04/K10, cardio codes rejected)
 *  - C-1 tiered confirm flow in handleCompleteVisit (danger intent on
 *    critical codes; no completeVisit without confirm; state reset +
 *    callNextWaiting after success)
 *  - protocol-template draft mapping (buildVisitProtocolDraftFromTemplate)
 *  - dialog-opening handlers (visitProtocol / dentalChart)
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import notify from '../../../services/notify';
import logger from '../../../utils/logger';
import { apiClient } from '../../../api/client';
import tokenManager from '../../../utils/tokenManager';
import { queueService } from '../../../services/queue';
import { printPanelTicket } from '../../../services/panelPrint';

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

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useDentistActions (PR-UI-15-5) — patient normalization', () => {
  it('resolvePatientId reads nested patient.id, then patient_id, then id', () => {
    const { result } = renderHook(() => useDentistActions(makeDeps()));
    expect(result.current.resolvePatientId({ patient: { id: 11 } })).toBe(11);
    expect(result.current.resolvePatientId({ patient_id: 22 })).toBe(22);
    expect(result.current.resolvePatientId({ id: 33 })).toBe(33);
    expect(result.current.resolvePatientId(null)).toBeNull();
    expect(result.current.resolvePatientId({})).toBeNull();
  });

  it('resolvePatientName falls back through patient_name → patient_fio → name → i18n default', () => {
    const { result } = renderHook(() => useDentistActions(makeDeps()));
    expect(result.current.resolvePatientName({ patient_name: 'A' })).toBe('A');
    expect(result.current.resolvePatientName({ patient_fio: 'B' })).toBe('B');
    expect(result.current.resolvePatientName({ name: 'C' })).toBe('C');
    expect(result.current.resolvePatientName(null)).toBe('dental.dental_panel_patient_default');
  });
});

describe('useDentistActions (PR-UI-15-5) — handlePatientSelect routing', () => {
  it('routes to visit tab when the patient has an active visit', () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    act(() => {
      result.current.handlePatientSelect({ patient_name: 'P', visit_id: 5 });
    });
    expect(deps.setSelectedPatient).toHaveBeenCalledWith(
      expect.objectContaining({ patient_name: 'P', patient_fio: 'P', visit_id: 5 }),
    );
    expect(deps.handleTabChange).toHaveBeenCalledWith('visit');
    expect(notify.info).not.toHaveBeenCalled();
  });

  it('shows no-visit notice and stays on patients tab without a visit', () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    act(() => {
      result.current.handlePatientSelect({ patient_name: 'P' });
    });
    expect(notify.info).toHaveBeenCalledWith('dental.no_active_visit');
    expect(deps.handleTabChange).toHaveBeenCalledWith('patients');
    expect(deps.handleTabChange).not.toHaveBeenCalledWith('visit');
  });
});

describe('useDentistActions (PR-UI-15-5) — C-3 critical ICD-10 gate', () => {
  it('matches critical dental codes by prefix (case-insensitive)', () => {
    const { result } = renderHook(() => useDentistActions(makeDeps()));
    expect(result.current.getCriticalDiagnosisWarning('K04.5')).toMatchObject({ code: 'K04', fullCode: 'K04.5' });
    expect(result.current.getCriticalDiagnosisWarning('k10.2')).toMatchObject({ code: 'K10', fullCode: 'K10.2'.toUpperCase() });
    expect(result.current.getCriticalDiagnosisWarning('K049')).toMatchObject({ code: 'K04' });
  });

  it('returns null for non-critical codes and non-string input', () => {
    const { result } = renderHook(() => useDentistActions(makeDeps()));
    expect(result.current.getCriticalDiagnosisWarning('I21.0')).toBeNull();
    expect(result.current.getCriticalDiagnosisWarning('')).toBeNull();
    expect(result.current.getCriticalDiagnosisWarning(null)).toBeNull();
    expect(result.current.getCriticalDiagnosisWarning(42)).toBeNull();
  });

  it('label is resolved through the i18n adapter (dental.dental_panel_critical_*)', () => {
    const { result } = renderHook(() => useDentistActions(makeDeps()));
    expect(result.current.getCriticalDiagnosisWarning('K04.1')?.label).toBe('dental.dental_panel_critical_K04');
  });
});

describe('useDentistActions (PR-UI-15-5) — handleCompleteVisit C-1 tiered confirm', () => {
  const patientWith = (extra: Partial<SelectedPatient>): SelectedPatient =>
    ({ doctor_queue_entry_id: 99, patient_name: 'P', ...extra }) as SelectedPatient;

  it('refuses without a selected patient', async () => {
    const deps = makeDeps({ selectedPatient: null });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleCompleteVisit();
    expect(notify.error).toHaveBeenCalledWith('dental.no_patient_for_complete');
    expect(queueService.completeVisit).not.toHaveBeenCalled();
  });

  it('refuses when the queue entry id cannot be resolved', async () => {
    const deps = makeDeps({ selectedPatient: { patient_name: 'P' } as SelectedPatient });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleCompleteVisit();
    expect(notify.error).toHaveBeenCalledWith('dental.no_queue_id_for_complete');
    expect(queueService.completeVisit).not.toHaveBeenCalled();
  });

  it('aborts when the user rejects the confirm dialog', async () => {
    const confirm = vi.fn(async () => false);
    const deps = makeDeps({ confirm, selectedPatient: patientWith({}) });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleCompleteVisit();
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(queueService.completeVisit).not.toHaveBeenCalled();
    expect(deps.handleTabChange).not.toHaveBeenCalled();
  });

  it('uses danger intent when the ICD-10 code is critical (K04)', async () => {
    const confirm = vi.fn(async () => false);
    const deps = makeDeps({
      confirm,
      selectedPatient: patientWith({ visitData: { icd10: 'K04.7' } }),
    });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleCompleteVisit();
    const options = confirm.mock.calls[0][0] as Record<string, unknown>;
    expect(options.intent).toBe('danger');
    expect(options.title).toContain('dental.dental_panel_critical_title');
  });

  it('uses primary intent for non-critical diagnoses', async () => {
    const confirm = vi.fn(async () => false);
    const deps = makeDeps({
      confirm,
      selectedPatient: patientWith({ visitData: { icd10: 'K02.1' } }),
    });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleCompleteVisit();
    const options = confirm.mock.calls[0][0] as Record<string, unknown>;
    expect(options.intent).toBe('primary');
  });

  it('completes the visit, resets state and auto-invites the next patient', async () => {
    const deps = makeDeps({
      selectedPatient: patientWith({
        patient_id: 42,
        visitData: { diagnosis: 'caries', icd10: 'K02.1', complaint: 'pain' },
      }),
    });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleCompleteVisit();

    expect(queueService.completeVisit).toHaveBeenCalledWith(99, {
      patient_id: 42,
      complaint: 'pain',
      diagnosis: 'caries',
      icd10: 'K02.1',
      services: [],
      notes: '',
    });
    expect(deps.setSelectedPatient).toHaveBeenCalledWith(null);
    expect(deps.setShowVisitProtocol).toHaveBeenCalledWith(false);
    expect(deps.setProtocolTemplateDraft).toHaveBeenCalledWith(null);
    expect(deps.handleTabChange).toHaveBeenCalledWith('queue');
    expect(queueService.callNextWaiting).toHaveBeenCalledWith('dentistry');
    expect(notify.success).toHaveBeenCalledWith('dental.dental_panel_next_patient_called:{"number":7}');
    expect(deps.setLoading).toHaveBeenCalledWith(false);
  });

  it('does not break the flow when callNextWaiting fails (visit already completed)', async () => {
    vi.mocked(queueService.callNextWaiting).mockRejectedValueOnce(new Error('boom'));
    const deps = makeDeps({ selectedPatient: patientWith({}) });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleCompleteVisit();
    expect(queueService.completeVisit).toHaveBeenCalledTimes(1);
    expect(deps.handleTabChange).toHaveBeenCalledWith('queue');
    expect(logger.warn).toHaveBeenCalled();
  });
});

describe('useDentistActions (PR-UI-15-5) — appointment table actions', () => {
  it('payment action shows the i18n TODO notice with the patient name', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    const event = { stopPropagation: vi.fn() } as unknown as React.MouseEvent<HTMLElement>;
    await result.current.handleAppointmentActionClick('payment', { patient_fio: 'Q' } as never, event);
    expect(notify.info).toHaveBeenCalledWith('dental.dental_panel_payment_todo:{"name":"Q"}');
  });

  it('call action errors when no queue entry id is available', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    const event = { stopPropagation: vi.fn() } as unknown as React.MouseEvent<HTMLElement>;
    await result.current.handleAppointmentActionClick('call', { patient_fio: 'Q' } as never, event);
    expect(notify.error).toHaveBeenCalledWith('dental.no_queue_id_for_visit');
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('call action posts to the doctor queue start-visit endpoint and reloads', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    const event = { stopPropagation: vi.fn() } as unknown as React.MouseEvent<HTMLElement>;
    await result.current.handleAppointmentActionClick(
      'call',
      { patient_fio: 'Q', doctor_queue_entry_id: 12 } as never,
      event,
    );
    expect(apiClient.post).toHaveBeenCalledWith('/doctor/queue/12/start-visit');
    expect(deps.loadDentistryAppointments).toHaveBeenCalledWith(true);
  });

  it('print action reports the print result through notify', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    const event = { stopPropagation: vi.fn() } as unknown as React.MouseEvent<HTMLElement>;
    await result.current.handleAppointmentActionClick('print', { patient_fio: 'Q' } as never, event);
    expect(printPanelTicket).toHaveBeenCalled();
    expect(notify.success).toHaveBeenCalledWith('printed');
  });

  it('row click requires a canonical visit id before switching to the visit tab', async () => {
    const ensureCanonicalVisitId = vi.fn(async () => null);
    const deps = makeDeps({ ensureCanonicalVisitId });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleAppointmentRowClick({ patient_fio: 'Q' } as never);
    expect(deps.setSelectedPatient).not.toHaveBeenCalled();
    expect(logger.error).toHaveBeenCalled();
  });

  it('row click switches to the visit tab once the visit id resolves', async () => {
    const ensureCanonicalVisitId = vi.fn(async () => 55);
    const deps = makeDeps({ ensureCanonicalVisitId });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleAppointmentRowClick({
      id: 1,
      patient_fio: 'Q',
      doctor_queue_entry_id: 12,
    } as never);
    expect(deps.setSelectedPatient).toHaveBeenCalledWith(
      expect.objectContaining({ visit_id: 55, patient_name: 'Q', source: 'appointments' }),
    );
    expect(deps.handleTabChange).toHaveBeenCalledWith('visit');
  });
});

describe('useDentistActions (PR-UI-15-5) — protocol templates', () => {
  it('buildVisitProtocolDraftFromTemplate maps template fields onto the EMR draft shape', () => {
    const { result } = renderHook(() => useDentistActions(makeDeps()));
    const draft = result.current.buildVisitProtocolDraftFromTemplate({
      name: 'T-name',
      description: 'T-desc',
      steps: [{ name: 'step-one' }, 'step-two'],
      materials: [{ name: 'anesthetic', quantity: '2', required: true }],
      anesthesia: [{ drug: 'lidocaine', dose: '2ml', required: true }],
      photos: [
        { type: 'before', description: 'before-shot' },
        { type: 'after', description: 'after-shot' },
      ],
      prescriptions: [{ medication: 'ibuprofen', dosage: '400mg' }],
      aftercare: 'rinse',
    }) as Record<string, any>;

    expect(draft.chiefComplaint).toBe('T-desc');
    expect(draft.historyOfPresentIllness).toBe('T-desc');
    expect(draft.procedures).toHaveLength(2);
    expect(draft.procedures[0].name).toBe('step-one');
    expect(draft.procedures[1].name).toBe('step-two');
    expect(draft.materials[0]).toMatchObject({ name: 'anesthetic', quantity: '2' });
    expect(draft.materials[0].notes).toBe('dental.dental_panel_required_material');
    expect(draft.anesthesia[0]).toMatchObject({ drug: 'lidocaine', dose: '2ml', required: true });
    expect(draft.photos.before).toHaveLength(1);
    expect(draft.photos.before[0].filename).toBe('before-shot');
    expect(draft.photos.after).toHaveLength(1);
    expect(draft.photos.during).toHaveLength(0);
    expect(draft.radiographs).toEqual([]);
    expect(draft.prescriptions[0]).toMatchObject({ medication: 'ibuprofen', dosage: '400mg' });
    expect(draft.recommendations).toBe('rinse');
    expect(draft.nextVisit).toEqual({ date: '', time: '', purpose: '' });
  });

  it('buildVisitProtocolDraftFromTemplate returns null without a template', () => {
    const { result } = renderHook(() => useDentistActions(makeDeps()));
    expect(result.current.buildVisitProtocolDraftFromTemplate(null)).toBeNull();
  });

  it('handleProtocolTemplateSelect stages the draft and opens the visit protocol screen', () => {
    const deps = makeDeps({
      selectedPatient: { patient_id: 3, patient_name: 'P', visit_id: 8 } as SelectedPatient,
    });
    const { result } = renderHook(() => useDentistActions(deps));
    act(() => {
      result.current.handleProtocolTemplateSelect({ name: 'T-name', description: 'D' });
    });
    expect(deps.setProtocolTemplateDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        patient_name: 'P',
        patient_id: 3,
        visit_id: 8,
        source: 'protocol-template',
        visitData: expect.objectContaining({ chiefComplaint: 'D' }),
      }),
    );
    expect(deps.setShowProtocolTemplates).toHaveBeenCalledWith(false);
    expect(deps.setShowVisitProtocol).toHaveBeenCalledWith(true);
  });
});

describe('useDentistActions (PR-UI-15-5) — dialog-opening handlers', () => {
  it('handleVisitProtocol requires a visit id (own or canonical)', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleVisitProtocol({ patient_name: 'P' });
    expect(notify.error).toHaveBeenCalledWith('dental.protocol_needs_visit_id');
    expect(deps.setShowVisitProtocol).not.toHaveBeenCalled();
  });

  it('handleVisitProtocol loads the backend protocol and merges visitData', async () => {
    const loadDentistVisitProtocolByVisitId = vi.fn(async () => ({
      visitData: { icd10: 'K02.1' },
      source: 'emr-v2',
    }));
    const deps = makeDeps({ loadDentistVisitProtocolByVisitId });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleVisitProtocol({ patient_name: 'P', visit_id: 77 });
    expect(loadDentistVisitProtocolByVisitId).toHaveBeenCalledWith(77, { patient_name: 'P', visit_id: 77 });
    expect(deps.setSelectedPatient).toHaveBeenCalledWith(
      expect.objectContaining({
        visit_id: 77,
        visitData: { icd10: 'K02.1' },
        source: 'emr-v2',
      }),
    );
    expect(deps.setShowVisitProtocol).toHaveBeenCalledWith(true);
  });

  it('handleDentalChart passes the chart payload and opens the chart dialog', () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    act(() => {
      result.current.handleDentalChart({ patient_name: 'P', dentalChart: { teeth: 32 } });
    });
    expect(deps.setDentalChartData).toHaveBeenCalledWith({ teeth: 32 });
    expect(deps.setShowDentalChart).toHaveBeenCalledWith(true);
  });

  it('handleTreatmentPlanner requires a visit id', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleTreatmentPlanner({ patient_name: 'P' });
    expect(notify.error).toHaveBeenCalledWith('dental.treatment_plan_needs_visit_id');
    expect(deps.setShowTreatmentPlanner).not.toHaveBeenCalled();
  });

  it('simple dialog openers flip exactly their own dialog flag', () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    act(() => {
      result.current.handleProtocolTemplates();
      result.current.handleReports();
    });
    expect(deps.setShowProtocolTemplates).toHaveBeenCalledWith(true);
    expect(deps.setShowReports).toHaveBeenCalledWith(true);
    expect(deps.setShowDiagnosisForm).not.toHaveBeenCalled();
    expect(deps.setShowPhotoArchive).not.toHaveBeenCalled();
  });
});

describe('useDentistActions (PR-UI-15-5) — source boundary', () => {
  it('keeps queue completion on the doctor queue endpoint (no registrar start-visit)', async () => {
    const deps = makeDeps({
      selectedPatient: { doctor_queue_entry_id: 5 } as SelectedPatient,
    });
    const { result } = renderHook(() => useDentistActions(deps));
    await result.current.handleCompleteVisit();
    const posted = vi.mocked(apiClient.post).mock.calls.map((c) => c[0]);
    expect(posted).toHaveLength(0); // completeVisit goes through queueService, not apiClient
    expect(queueService.completeVisit).toHaveBeenCalledWith(5, expect.anything());
    expect(posted.join(' ')).not.toContain('/registrar/queue');
  });

  it('exposes every extracted handler on its return object', () => {
    const { result } = renderHook(() => useDentistActions(makeDeps()));
    const h = result.current;
    expect(typeof h.resolvePatientId).toBe('function');
    expect(typeof h.resolvePatientName).toBe('function');
    expect(typeof h.handleAppointmentRowClick).toBe('function');
    expect(typeof h.handleAppointmentActionClick).toBe('function');
    expect(typeof h.handlePatientSelect).toBe('function');
    expect(typeof h.getCriticalDiagnosisWarning).toBe('function');
    expect(typeof h.handleCompleteVisit).toBe('function');
    expect(typeof h.handleDiagnosis).toBe('function');
    expect(typeof h.handleVisitProtocol).toBe('function');
    expect(typeof h.handlePhotoArchive).toBe('function');
    expect(typeof h.handleProtocolTemplates).toBe('function');
    expect(typeof h.buildVisitProtocolDraftFromTemplate).toBe('function');
    expect(typeof h.handleProtocolTemplateSelect).toBe('function');
    expect(typeof h.handleReports).toBe('function');
    expect(typeof h.handleDentalChart).toBe('function');
    expect(typeof h.handleTreatmentPlanner).toBe('function');
  });
});

describe('useDentistActions (PR-UI-15-5) — loading gate around loadData', () => {
  it('waitFor helper sanity (panel still owns the loading effect)', async () => {
    const deps = makeDeps();
    renderHook(() => useDentistActions(deps));
    await waitFor(() => expect(deps.setLoading).not.toHaveBeenCalled());
  });
});
