import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import { useDermatologyPatientHistory } from '../useDermatologyPatientHistory';

vi.mock('../../api/client', () => ({ api: { get: vi.fn() } }));

const mockedGet = vi.mocked(api.get);

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => { resolve = complete; });
  return { promise, resolve };
}

function response(data: unknown) {
  return { data, status: 200 } as never;
}

describe('useDermatologyPatientHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not request general history before a patient is selected', () => {
    const { result } = renderHook(() => useDermatologyPatientHistory(null));

    expect(mockedGet).not.toHaveBeenCalled();
    expect(result.current).toMatchObject({
      appointments: [],
      skinExaminations: [],
      cosmeticProcedures: [],
      loading: false,
      ready: false,
    });
  });

  it('requests the combined derma history and appointments with the selected patient ID', async () => {
    mockedGet.mockResolvedValue(response({}));
    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(mockedGet).toHaveBeenNthCalledWith(1, '/patients/42/appointments');
    expect(mockedGet).toHaveBeenNthCalledWith(2, '/derma/history', {
      params: { patient_id: '42', limit: 10 },
    });
    expect(mockedGet).toHaveBeenCalledTimes(2);
  });

  it('splits the combined derma history response into both sections', async () => {
    mockedGet.mockImplementation((url) => {
      if (String(url).includes('/appointments')) {
        return Promise.resolve(response([{ id: 7, appointment_date: '2026-01-05' }])) as never;
      }
      return Promise.resolve(response({
        examinations: [{ id: 'emr-1', diagnosis: 'SYNTHETIC-Diagnosis' }],
        procedures: [{ id: 'emr-1-0', procedure_type: 'SYNTHETIC-Procedure' }],
      })) as never;
    });
    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.appointments).toEqual([{ id: 7, appointment_date: '2026-01-05' }]);
    expect(result.current.skinExaminations).toEqual([{ id: 'emr-1', diagnosis: 'SYNTHETIC-Diagnosis' }]);
    expect(result.current.cosmeticProcedures).toEqual([{ id: 'emr-1-0', procedure_type: 'SYNTHETIC-Procedure' }]);
  });

  it('hides the previous patient history immediately and ignores its late response', async () => {
    const requests = new Map<string, Array<ReturnType<typeof deferred>>>();
    mockedGet.mockImplementation((url, config) => {
      const id = String(url).includes('/appointments')
        ? String(url).match(/patients\/(\d+)/)?.[1] || ''
        : String((config?.params as Record<string, unknown> | undefined)?.patient_id || '');
      const request = deferred<unknown>();
      const pending = requests.get(id) || [];
      pending.push(request);
      requests.set(id, pending);
      return request.promise as never;
    });

    const { result, rerender } = renderHook(
      ({ patientId }) => useDermatologyPatientHistory(patientId),
      { initialProps: { patientId: '1' as string | null } },
    );

    await waitFor(() => expect(requests.get('1')).toHaveLength(2));
    rerender({ patientId: '2' });
    await waitFor(() => expect(requests.get('2')).toHaveLength(2));
    expect(result.current.appointments).toEqual([]);
    expect(result.current.skinExaminations).toEqual([]);
    expect(result.current.cosmeticProcedures).toEqual([]);

    await act(async () => {
      requests.get('2')?.[0].resolve(response([{ id: 22, appointment_date: '2026-01-02' }]));
      requests.get('2')?.[1].resolve(response({
        examinations: [{ id: 22, diagnosis: 'SYNTHETIC-Diagnosis-2' }],
        procedures: [{ id: 22, procedure_type: 'SYNTHETIC-Procedure-2' }],
      }));
    });
    await waitFor(() => expect(result.current.ready).toBe(true));

    await act(async () => {
      requests.get('1')?.[0].resolve(response([{ id: 11, appointment_date: '2025-01-01' }]));
      requests.get('1')?.[1].resolve(response({
        examinations: [{ id: 11, diagnosis: 'SYNTHETIC-Diagnosis-1' }],
        procedures: [{ id: 11, procedure_type: 'SYNTHETIC-Procedure-1' }],
      }));
    });

    expect(result.current.appointments).toEqual([{ id: 22, appointment_date: '2026-01-02' }]);
    expect(result.current.skinExaminations).toEqual([{ id: 22, diagnosis: 'SYNTHETIC-Diagnosis-2' }]);
    expect(result.current.cosmeticProcedures).toEqual([{ id: 22, procedure_type: 'SYNTHETIC-Procedure-2' }]);
  });
});
