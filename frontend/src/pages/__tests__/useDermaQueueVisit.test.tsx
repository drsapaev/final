/**
 * DERMAQUEUE-FE-001 (audit 3892, post-merge group 10) — fail-first
 * regression for the dermatology queue → visit handoff:
 *
 * The dermatologist's live queue must offer a Start Visit action after
 * calling a patient (dentistry already wires `onStartVisit`). The handoff
 * resolves the canonical patient/visit through the backend
 * `POST /doctor/queue/{entry_id}/start-visit` ack and fails closed on any
 * unconfirmed or identity-less response.
 *
 * Red-first: the hook does not exist on the pre-fix source, so this suite
 * fails to import — the documented red reason. Positive/negative branches
 * mirror useDentistActions' start-visit contract.
 */
import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useDermaQueueVisit } from '../useDermaQueueVisit';
import { queueService } from '../../services/queue';

vi.mock('../../services/queue', () => ({
  queueService: { startVisit: vi.fn() },
}));
vi.mock('../../services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const mockedStartVisit = vi.mocked(queueService.startVisit);

import notifyService from '../../services/notify';

const CALLED_PATIENT = { id: 17, name: 'SYNTHETIC CALLED PATIENT', number: 3 };

describe('useDermaQueueVisit — start-visit handoff (DERMAQUEUE-FE-001)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts the visit from a confirmed ack and hands the canonical patient/visit to the panel', async () => {
    const selectPatient = vi.fn();
    mockedStartVisit.mockResolvedValue({
      success: true,
      entry_id: 17,
      patient_id: 9,
      visit_id: 77,
      status: 'in_progress',
    } as never);

    const { result } = renderHook(() => useDermaQueueVisit({ selectPatient }));
    const started = await result.current(CALLED_PATIENT);

    expect(started).toBe(true);
    expect(mockedStartVisit).toHaveBeenCalledWith(17);
    expect(selectPatient).toHaveBeenCalledTimes(1);
    expect(selectPatient.mock.calls[0][0]).toMatchObject({
      id: 9,
      patient_id: 9,
      visit_id: 77,
      doctor_queue_entry_id: 17,
      queue_entry_id: 17,
      patient_name: 'SYNTHETIC CALLED PATIENT',
      source: 'queue',
      status: 'in_progress',
    });
    expect(notifyService.error).not.toHaveBeenCalled();
  });

  it('fails closed when the ack is not an explicit success', async () => {
    const selectPatient = vi.fn();
    mockedStartVisit.mockResolvedValue({ success: false } as never);

    const { result } = renderHook(() => useDermaQueueVisit({ selectPatient }));
    const started = await result.current(CALLED_PATIENT);

    expect(started).toBe(false);
    expect(selectPatient).not.toHaveBeenCalled();
    expect(notifyService.error).toHaveBeenCalledWith('derma.derma_panel_start_visit_failed');
  });

  it('fails closed when the ack misses the canonical patient/visit identity', async () => {
    const selectPatient = vi.fn();
    mockedStartVisit.mockResolvedValue({ success: true, patient_id: 9 } as never);

    const { result } = renderHook(() => useDermaQueueVisit({ selectPatient }));
    const started = await result.current(CALLED_PATIENT);

    expect(started).toBe(false);
    expect(selectPatient).not.toHaveBeenCalled();
    expect(notifyService.error).toHaveBeenCalledWith('derma.derma_panel_start_visit_failed');
  });

  it('fails closed when the queue entry id is missing', async () => {
    const selectPatient = vi.fn();

    const { result } = renderHook(() => useDermaQueueVisit({ selectPatient }));
    const started = await result.current({ id: null, name: 'X', number: 1 });

    expect(started).toBe(false);
    expect(selectPatient).not.toHaveBeenCalled();
    expect(mockedStartVisit).not.toHaveBeenCalled();
    expect(notifyService.error).toHaveBeenCalledWith('derma.no_queue_id_for_visit');
  });

  it('fails closed when the start-visit request throws', async () => {
    const selectPatient = vi.fn();
    mockedStartVisit.mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useDermaQueueVisit({ selectPatient }));
    const started = await result.current(CALLED_PATIENT);

    expect(started).toBe(false);
    expect(selectPatient).not.toHaveBeenCalled();
    expect(notifyService.error).toHaveBeenCalledWith('derma.derma_panel_start_visit_failed');
  });
});
