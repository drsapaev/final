import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import notify from '../../../services/notify';
import logger from '../../../utils/logger';
import { apiClient } from '../../../api/client';

import { useDentistActions } from '../useDentistActions';
import type { Appointment } from '../../../types/domain/clinic';

/**
 * DENTWORK-FE-001 (audit 2026-11-06, PR 3892): an appointment/queue row
 * carries both the queue entry id and the real patient_id. Selecting a row
 * must propagate patient_id into SelectedPatient so patient-scoped history
 * and completion payloads never use the queue entry id as patient identity.
 */
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
  confirm: vi.fn(async (_options: Record<string, unknown>) => true),
  setLoading: vi.fn(),
  selectedPatient: null,
  setSelectedPatient: vi.fn(),
  handleTabChange: vi.fn(),
  ensureCanonicalVisitId: vi.fn(async () => '41'),
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

// Queue entry id '101' and patient id '7' are deliberately different values:
// the whole point of DENTWORK-FE-001 is that they must never be conflated.
const queueRow = {
  id: '101',
  appointment_id: null,
  visit_id: '41',
  patient_id: '7',
  patient_fio: 'SYNTHETIC Dental Patient',
  patient_phone: 'SYNTHETIC-PHONE',
  number: '101',
} as Appointment;

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useDentistActions — appointment row patient identity (DENTWORK-FE-001)', () => {
  it('propagates the row patient_id (not the queue entry id) when a row click opens the visit', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));

    await act(async () => {
      await result.current.handleAppointmentRowClick(queueRow);
    });

    expect(deps.setSelectedPatient).toHaveBeenCalledTimes(1);
    expect(deps.setSelectedPatient).toHaveBeenCalledWith(
      expect.objectContaining({ patient_id: '7', id: '101', visit_id: '41' }),
    );
    expect(deps.handleTabChange).toHaveBeenCalledWith('visit');
  });

  it('propagates the row patient_id on the queue-row complete action path', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));

    await act(async () => {
      await result.current.handleAppointmentActionClick('complete', queueRow, {
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent<HTMLElement>);
    });

    expect(deps.setSelectedPatient).toHaveBeenCalledTimes(1);
    expect(deps.setSelectedPatient).toHaveBeenCalledWith(
      expect.objectContaining({ patient_id: '7', id: '101', visit_id: '41' }),
    );
    expect(deps.handleTabChange).toHaveBeenCalledWith('visit');
  });

  it('resolves the completion payload patient id from patient_id, not the queue entry id', async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useDentistActions(deps));

    await act(async () => {
      await result.current.handleAppointmentRowClick(queueRow);
    });
    const selected = vi.mocked(deps.setSelectedPatient).mock.calls[0][0] as Record<string, unknown>;

    expect(result.current.resolvePatientId(selected)).toBe('7');
    await waitFor(() => expect(apiClient.post).not.toHaveBeenCalled());
    expect(notify.error).not.toHaveBeenCalledWith('dental.no_queue_id_for_visit');
    expect(logger.warn).not.toHaveBeenCalledWith('[Dentist] Could not resolve canonical visit id');
  });
});
