/**
 * Audit 3892 round 1 — fail-first regression for DENTWORK-FE-001:
 * the dentist appointments table maps the queue entry id into the patient
 * identity slot. Selecting a row (view / complete actions) must carry the
 * canonical `patient_id` so the visit history lookup and the queue
 * completion payload identify the patient, not the queue entry.
 */
import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useDentistActions } from '../useDentistActions';

vi.mock('../../../services/notify', () => ({
  default: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

type Deps = Parameters<typeof useDentistActions>[0];

const makeDeps = (overrides: Partial<Deps> = {}): Deps => ({
  tI18n: t,
  confirm: vi.fn(async (_options: Record<string, unknown>) => true),
  setLoading: vi.fn(),
  selectedPatient: null,
  setSelectedPatient: vi.fn(),
  handleTabChange: vi.fn(),
  ensureCanonicalVisitId: vi.fn(async () => 55),
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

// Queue entry id 91 belongs to patient 23 — the two must never be conflated.
const queueRow = {
  id: 91,
  patient_id: 23,
  visit_id: 77,
  patient_fio: 'SYNTHETIC Patient',
  doctor_queue_entry_id: 5,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useDentistActions patient identity (DENTWORK-FE-001, audit 3892 round 1)', () => {
  it('row click selects the patient with the canonical patient_id, not the queue entry id', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));

    await result.current.handleAppointmentRowClick(queueRow as never);

    expect(deps.setSelectedPatient).toHaveBeenCalledWith(expect.objectContaining({
      patient_id: 23,
      visit_id: 55,
      source: 'appointments',
    }));
    expect(deps.handleTabChange).toHaveBeenCalledWith('visit');
  });

  it('complete action selects the patient with the canonical patient_id, not the queue entry id', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));
    const event = { stopPropagation: vi.fn() } as unknown as React.MouseEvent<HTMLElement>;

    await result.current.handleAppointmentActionClick('complete', queueRow as never, event);

    expect(deps.setSelectedPatient).toHaveBeenCalledWith(expect.objectContaining({
      patient_id: 23,
      visit_id: 55,
      source: 'appointments',
    }));
    expect(deps.handleTabChange).toHaveBeenCalledWith('visit');
  });
});
