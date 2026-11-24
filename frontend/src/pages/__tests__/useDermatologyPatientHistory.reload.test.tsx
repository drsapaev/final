/**
 * DERMAHIST-FE-003 (owner registry #4063; fourteenth review group) —
 * runtime pins for the history-refresh repair mechanics.
 *
 * The panel binding (see DermatologistPanel.historyReload.contract.test)
 * invokes the hook's `reload()` on EMR persisted. These runtime tests pin
 * the hook mechanics the repair relies on:
 *   - `reload()` refetches the SAME patient's history and updates the
 *     snapshot (the fresh request + updated count after a successful
 *     persist);
 *   - the request-generation guard discards a late response for a
 *     previous patient — no cross-patient stale overwrite;
 * and the persist gating (failed EMR writes never invoke the parent
 * refresh) is pinned in the contract suite.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMock = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('../../api/client', () => ({ api: { get: apiMock.get } }));
vi.mock('../../utils/logger', () => ({ default: { warn: vi.fn() } }));

import { useDermatologyPatientHistory } from '../useDermatologyPatientHistory';

const envelope = (items: unknown[]) => ({
  data: { items, total: items.length, page: 1, size: 20, pages: 1 },
});

const exam = (id: string) => ({ id, examination_date: '2026-11-16', diagnosis: `dx-${id}` });

type Responder = (url: string, patientId: string) => Promise<{ data: unknown }>;
let responder: Responder = async () => ({ data: [] });

apiMock.get.mockImplementation((url: string, config?: { params?: { patient_id?: string | number } }) => {
  const patientId = String(config?.params?.patient_id ?? '');
  return responder(url, patientId);
});

beforeEach(() => {
  apiMock.get.mockClear();
  responder = async () => ({ data: [] });
});

describe('DERMAHIST-FE-003 — history refresh mechanics', () => {
  it('reload() refetches the same patient and updates the snapshot with the new count', async () => {
    let exams: unknown[] = [exam('emr-1')];
    responder = (url, patientId) => {
      if (url.endsWith('/appointments')) return Promise.resolve({ data: [] });
      if (url === '/derma/examinations') {
        return Promise.resolve(envelope(patientId === '7' ? exams : []));
      }
      return Promise.resolve(envelope([]));
    };

    const { result } = renderHook(() => useDermatologyPatientHistory('7'));
    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.skinExaminations).toHaveLength(1);
    expect(result.current.skinExaminationsTotal).toBe(1);

    // A second canonical EMR is persisted server-side…
    exams = [exam('emr-1'), exam('emr-2')];
    // …and the panel binding calls reload() after the successful persist.
    act(() => { result.current.reload(); });

    await waitFor(() => expect(result.current.skinExaminations).toHaveLength(2));
    expect(result.current.skinExaminationsTotal).toBe(2);
    const examCalls = apiMock.get.mock.calls.filter(
      ([url, config]) => url === '/derma/examinations'
        && String((config as { params?: { patient_id?: string | number } })?.params?.patient_id) === '7',
    );
    expect(examCalls.length).toBeGreaterThanOrEqual(2);
  });

  it('a late response for the previous patient never overwrites the current snapshot', async () => {
    let resolveSeven: (value: { data: unknown }) => void = () => {};
    const deferredSeven = new Promise<{ data: unknown }>((resolve) => { resolveSeven = resolve; });
    responder = (url, patientId) => {
      if (url.endsWith('/appointments')) return Promise.resolve({ data: [] });
      if (url === '/derma/examinations') {
        return patientId === '7' ? deferredSeven : Promise.resolve(envelope([exam('emr-9')]));
      }
      return Promise.resolve(envelope([]));
    };

    const { result, rerender } = renderHook(
      ({ pid }: { pid: string | null }) => useDermatologyPatientHistory(pid),
      { initialProps: { pid: '7' } },
    );
    await waitFor(() => expect(result.current.loading).toBe(true));

    // The clinician switches to another patient while 7's fetch is in flight.
    rerender({ pid: '9' });
    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.skinExaminations.map((row) => row.id)).toEqual(['emr-9']);

    // The stale response for patient 7 lands late — it must be discarded.
    resolveSeven(envelope([exam('emr-1'), exam('emr-2'), exam('emr-3')]));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.ready).toBe(true);
    expect(result.current.skinExaminations.map((row) => row.id)).toEqual(['emr-9']);
  });
});
