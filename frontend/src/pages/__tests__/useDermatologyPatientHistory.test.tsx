import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import { useDermatologyPatientHistory } from '../useDermatologyPatientHistory';

vi.mock('../../api/client', () => ({ api: { get: vi.fn() } }));
vi.mock('../../utils/logger', () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));

const mockedGet = vi.mocked(api.get);

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => { resolve = complete; });
  return { promise, resolve };
}

function response(data: unknown, status = 200) {
  return { data, status } as never;
}

const DERMATOLOGY_EMR = {
  id: 900,
  created_at: '2026-09-20T10:00:00',
  diagnosis_main: 'SYNTHETIC EMR diagnosis',
  data: {
    specialty: 'dermatology',
    specialty_data: {
      skin_type: 'dry',
      skin_condition: 'Чувствительная кожа',
      cosmetic_procedures: [
        { procedure_date: '2026-09-20', procedure_type: 'laser', area_treated: 'Щеки' },
      ],
    },
  },
};

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

  it('requests the EMR history and both legacy fallback sources with the selected patient ID', async () => {
    mockedGet.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/patients/42/appointments') return response([]);
      if (path === '/v2/emr/patient/42') return response([]);
      if (path === '/derma/examinations') return response([]);
      if (path === '/derma/procedures') return response([]);
      throw new Error(`unexpected GET ${path}`);
    });

    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(mockedGet).toHaveBeenCalledWith('/patients/42/appointments');
    expect(mockedGet).toHaveBeenCalledWith('/v2/emr/patient/42', { params: { limit: 20 } });
    expect(mockedGet).toHaveBeenCalledWith('/derma/examinations', {
      params: { patient_id: '42', limit: 10 },
    });
    expect(mockedGet).toHaveBeenCalledWith('/derma/procedures', {
      params: { patient_id: '42', limit: 10 },
    });
  });

  it('merges EMR and legacy rows, most recent first, skipping non-dermatology and empty EMRs', async () => {
    mockedGet.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/patients/42/appointments') return response([]);
      if (path === '/v2/emr/patient/42') {
        return response([{ visit_id: 900 }, { visit_id: 901 }, { visit_id: 902 }, { visit_id: 903 }]);
      }
      if (path === '/v2/emr/900') return response(DERMATOLOGY_EMR);
      if (path === '/v2/emr/901') {
        // Non-dermatology EMR: never contributes to derma history.
        return response({
          id: 901,
          created_at: '2026-09-21T10:00:00',
          diagnosis_main: 'cardio diagnosis',
          data: { specialty: 'cardiology', specialty_data: { skin_type: 'oily' } },
        });
      }
      if (path === '/v2/emr/902') {
        // Dermatology EMR without derma content: skipped.
        return response({
          id: 902,
          created_at: '2026-09-22T10:00:00',
          data: { specialty: 'dermatology', specialty_data: {} },
        });
      }
      if (path === '/v2/emr/903') return response(null, 404);
      if (path === '/derma/examinations') {
        return response([
          { id: 7, examination_date: '2026-09-25', diagnosis: 'SYNTHETIC legacy newer' },
          { id: 8, examination_date: '2026-09-01', diagnosis: 'SYNTHETIC legacy older' },
        ]);
      }
      if (path === '/derma/procedures') {
        return response([{ id: 9, procedure_date: '2026-09-02', procedure_type: 'peel' }]);
      }
      throw new Error(`unexpected GET ${path}`);
    });

    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.skinExaminations).toEqual([
      { id: 7, examination_date: '2026-09-25', diagnosis: 'SYNTHETIC legacy newer' },
      {
        id: 'emr-900',
        examination_date: '2026-09-20',
        skin_type: 'dry',
        skin_condition: 'Чувствительная кожа',
        diagnosis: 'SYNTHETIC EMR diagnosis',
      },
      { id: 8, examination_date: '2026-09-01', diagnosis: 'SYNTHETIC legacy older' },
    ]);
    expect(result.current.cosmeticProcedures).toEqual([
      { id: 'emr-900-0', procedure_date: '2026-09-20', procedure_type: 'laser', area_treated: 'Щеки' },
      { id: 9, procedure_date: '2026-09-02', procedure_type: 'peel' },
    ]);
    expect(result.current.error).toBe(false);
  });

  it('falls back to legacy rows when the EMR history request fails', async () => {
    mockedGet.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/patients/42/appointments') return response([]);
      if (path === '/v2/emr/patient/42') throw new Error('EMR unavailable');
      if (path === '/derma/examinations') {
        return response([{ id: 7, examination_date: '2026-09-25', diagnosis: 'legacy only' }]);
      }
      if (path === '/derma/procedures') return response([]);
      throw new Error(`unexpected GET ${path}`);
    });

    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.skinExaminations).toEqual([
      { id: 7, examination_date: '2026-09-25', diagnosis: 'legacy only' },
    ]);
    expect(result.current.cosmeticProcedures).toEqual([]);
    expect(result.current.error).toBe(true);
  });

  it('hides the previous patient history immediately and ignores its late response', async () => {
    const requests = new Map<string, Array<ReturnType<typeof deferred>>>();
    mockedGet.mockImplementation((url: unknown) => {
      const path = String(url);
      const key = path.startsWith('/patients/')
        ? `appointments-${path.match(/patients\/(\d+)/)?.[1] || ''}`
        : path.startsWith('/v2/emr/patient/')
          ? `emr-${path.match(/v2\/emr\/patient\/(\d+)/)?.[1] || ''}`
          : path.startsWith('/v2/emr/')
            ? `visit-${path.match(/v2\/emr\/(\d+)/)?.[1] || ''}`
            : `legacy-${path}`;
      const request = deferred<unknown>();
      const pending = requests.get(key) || [];
      pending.push(request);
      requests.set(key, pending);
      return request.promise as never;
    });

    const { result, rerender } = renderHook(
      ({ patientId }) => useDermatologyPatientHistory(patientId),
      { initialProps: { patientId: '1' as string | null } },
    );

    await waitFor(() => expect(requests.get('appointments-1')).toHaveLength(1));
    rerender({ patientId: '2' });
    await waitFor(() => expect(requests.get('appointments-2')).toHaveLength(1));
    expect(result.current.appointments).toEqual([]);
    expect(result.current.skinExaminations).toEqual([]);
    expect(result.current.cosmeticProcedures).toEqual([]);

    await act(async () => {
      requests.get('appointments-2')?.[0].resolve(response([{ id: 22, appointment_date: '2026-01-02' }]));
      requests.get('emr-2')?.[0].resolve(response([]));
      requests.get('legacy-/derma/examinations')?.[1].resolve(response([{ id: 22, diagnosis: 'SYNTHETIC-Diagnosis-2' }]));
      requests.get('legacy-/derma/procedures')?.[1].resolve(response([{ id: 22, procedure_type: 'SYNTHETIC-Procedure-2' }]));
    });
    await waitFor(() => expect(result.current.ready).toBe(true));

    await act(async () => {
      requests.get('appointments-1')?.[0].resolve(response([{ id: 11, appointment_date: '2025-01-01' }]));
      requests.get('emr-1')?.[0].resolve(response([{ visit_id: 111 }]));
      requests.get('visit-111')?.[0].resolve(response({
        id: 111,
        created_at: '2025-01-01T10:00:00',
        data: { specialty: 'dermatology', specialty_data: { skin_type: 'dry' } },
      }));
      requests.get('legacy-/derma/examinations')?.[0].resolve(response([{ id: 11, diagnosis: 'SYNTHETIC-Diagnosis-1' }]));
      requests.get('legacy-/derma/procedures')?.[0].resolve(response([{ id: 11, procedure_type: 'SYNTHETIC-Procedure-1' }]));
    });

    expect(result.current.appointments).toEqual([{ id: 22, appointment_date: '2026-01-02' }]);
    expect(result.current.skinExaminations).toEqual([
      { id: 22, diagnosis: 'SYNTHETIC-Diagnosis-2' },
    ]);
    expect(result.current.cosmeticProcedures).toEqual([{ id: 22, procedure_type: 'SYNTHETIC-Procedure-2' }]);
  });
});
