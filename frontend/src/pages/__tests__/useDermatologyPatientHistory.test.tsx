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

/** Canonical page envelope (FileList contract) served by the derma GETs. */
function envelope<T>(items: T[], total: number, page: number, pages: number) {
  return response({ items, total, page, size: 20, pages });
}

function paramsOf(config: unknown): { page?: number; patient_id?: string } {
  return (config as { params?: { page?: number; patient_id?: string } } | undefined)?.params ?? {};
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
      skinExaminationsTotal: 0,
      cosmeticProceduresTotal: 0,
      hasMoreExaminations: false,
      hasMoreProcedures: false,
      loading: false,
      ready: false,
    });
  });

  it('requests only the server-side union pages with the selected patient ID', async () => {
    mockedGet.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/patients/42/appointments') return response([]);
      if (path === '/derma/examinations') return envelope([], 0, 1, 0);
      if (path === '/derma/procedures') return envelope([], 0, 1, 0);
      throw new Error(`unexpected GET ${path}`);
    });

    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(mockedGet).toHaveBeenCalledWith('/patients/42/appointments');
    expect(mockedGet).toHaveBeenCalledWith('/derma/examinations', {
      params: { patient_id: '42', page: 1, size: 20 },
    });
    expect(mockedGet).toHaveBeenCalledWith('/derma/procedures', {
      params: { patient_id: '42', page: 1, size: 20 },
    });
    // P2-4b canonical: the union is server-side — the hook must not fetch
    // the EMR v2 endpoints directly (review follow-up on #3490/#3491).
    expect(mockedGet.mock.calls.map(([url]) => String(url))).not.toContain('/v2/emr/patient/42');
  });

  it('serves the union rows as returned and exposes exact totals', async () => {
    mockedGet.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/patients/42/appointments') return response([{ id: 1, appointment_date: '2026-09-01' }]);
      if (path === '/derma/examinations') {
        return envelope([
          { id: 'emr-900', examination_date: '2026-09-25', skin_type: 'dry', diagnosis: 'Розацеа' },
          { id: 7, examination_date: '2026-09-01', diagnosis: 'legacy' },
        ], 25, 1, 2);
      }
      if (path === '/derma/procedures') {
        return envelope([{ id: 'emr-900-0', procedure_date: '2026-09-25', procedure_type: 'laser' }], 1, 1, 1);
      }
      throw new Error(`unexpected GET ${path}`);
    });

    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.skinExaminations).toHaveLength(2);
    expect(result.current.skinExaminations[0]).toMatchObject({ id: 'emr-900', diagnosis: 'Розацеа' });
    expect(result.current.skinExaminationsTotal).toBe(25);
    expect(result.current.hasMoreExaminations).toBe(true);
    expect(result.current.cosmeticProcedures).toHaveLength(1);
    expect(result.current.cosmeticProceduresTotal).toBe(1);
    expect(result.current.hasMoreProcedures).toBe(false);
    expect(result.current.error).toBe(false);
  });

  it('loadMore appends the next union page without duplicates and stops at total', async () => {
    const examinationPages = [
      envelope([
        { id: 'emr-1', examination_date: '2026-09-25' },
        { id: 'emr-2', examination_date: '2026-09-24' },
      ], 3, 1, 2),
      envelope([
        { id: 'emr-3', examination_date: '2026-09-23' },
        { id: 'emr-2', examination_date: '2026-09-24' }, // defensive: duplicate id
      ], 3, 2, 2),
    ];
    mockedGet.mockImplementation(async (url: unknown, config?: unknown) => {
      const path = String(url);
      if (path === '/patients/42/appointments') return response([]);
      if (path === '/derma/examinations') {
        const page = paramsOf(config).page ?? 1;
        const payload = examinationPages[page - 1];
        if (!payload) throw new Error(`unexpected page ${page}`);
        return payload;
      }
      if (path === '/derma/procedures') return envelope([], 0, 1, 0);
      throw new Error(`unexpected GET ${path}`);
    });

    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.hasMoreExaminations).toBe(true);

    await act(async () => { result.current.loadMoreExaminations(); });

    await waitFor(() => expect(result.current.loadingMoreExaminations).toBe(false));
    expect(result.current.skinExaminations.map((row) => row.id)).toEqual(['emr-1', 'emr-2', 'emr-3']);
    expect(result.current.skinExaminationsTotal).toBe(3);
    expect(result.current.hasMoreExaminations).toBe(false);

    const callsBefore = mockedGet.mock.calls.length;
    await act(async () => { result.current.loadMoreExaminations(); });
    expect(mockedGet.mock.calls.length).toBe(callsBefore);
  });

  it('a failed loadMore keeps the loaded history and clears the in-flight flag', async () => {
    let failNext = false;
    mockedGet.mockImplementation(async (url: unknown, config?: unknown) => {
      const path = String(url);
      if (path === '/patients/42/appointments') return response([]);
      if (path === '/derma/procedures') return envelope([], 0, 1, 0);
      if (path === '/derma/examinations') {
        if ((paramsOf(config).page ?? 1) > 1 || failNext) throw new Error('page unavailable');
        return envelope([{ id: 1, examination_date: '2026-09-25' }], 2, 1, 2);
      }
      throw new Error(`unexpected GET ${path}`);
    });

    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    failNext = true;
    await act(async () => { result.current.loadMoreExaminations(); });

    await waitFor(() => expect(result.current.loadingMoreExaminations).toBe(false));
    expect(result.current.skinExaminations).toEqual([{ id: 1, examination_date: '2026-09-25' }]);
    expect(result.current.skinExaminationsTotal).toBe(2);
    expect(result.current.hasMoreExaminations).toBe(true);
    expect(result.current.error).toBe(false);
  });

  it('keeps the remaining sections alive when one history endpoint fails', async () => {
    mockedGet.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/patients/42/appointments') {
        return response([{ id: 5, appointment_date: '2026-09-01' }]);
      }
      if (path === '/derma/examinations') throw new Error('examinations unavailable');
      if (path === '/derma/procedures') {
        return envelope([{ id: 9, procedure_date: '2026-09-02', procedure_type: 'peel' }], 1, 1, 1);
      }
      throw new Error(`unexpected GET ${path}`);
    });

    const { result } = renderHook(() => useDermatologyPatientHistory(42));

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.appointments).toEqual([{ id: 5, appointment_date: '2026-09-01' }]);
    expect(result.current.skinExaminations).toEqual([]);
    expect(result.current.skinExaminationsTotal).toBe(0);
    expect(result.current.cosmeticProcedures).toEqual([
      { id: 9, procedure_date: '2026-09-02', procedure_type: 'peel' },
    ]);
    expect(result.current.error).toBe(true);
  });

  it('hides the previous patient history immediately and ignores its late responses', async () => {
    const requests = new Map<string, Array<ReturnType<typeof deferred>>>();
    mockedGet.mockImplementation((url: unknown, config?: unknown) => {
      const path = String(url);
      const params = paramsOf(config);
      const patient = String(params.patient_id ?? '');
      const suffix = params.page ? `-p${params.page}` : '';
      const key = path.startsWith('/patients/')
        ? `appointments-${path.match(/patients\/(\d+)/)?.[1] || ''}`
        : `history-${path}-${patient}${suffix}`;
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
      requests.get('history-/derma/examinations-2-p1')?.[0].resolve(envelope([
        { id: 22, examination_date: '2026-01-02', diagnosis: 'SYNTHETIC-Diagnosis-2' },
      ], 1, 1, 1));
      requests.get('history-/derma/procedures-2-p1')?.[0].resolve(envelope([
        { id: 23, procedure_date: '2026-01-02', procedure_type: 'SYNTHETIC-Procedure-2' },
      ], 1, 1, 1));
    });
    await waitFor(() => expect(result.current.ready).toBe(true));

    await act(async () => {
      requests.get('appointments-1')?.[0].resolve(response([{ id: 11, appointment_date: '2025-01-01' }]));
      requests.get('history-/derma/examinations-1-p1')?.[0].resolve(envelope([
        { id: 11, examination_date: '2025-01-01', diagnosis: 'SYNTHETIC-Diagnosis-1' },
      ], 1, 1, 1));
      requests.get('history-/derma/procedures-1-p1')?.[0].resolve(envelope([
        { id: 12, procedure_date: '2025-01-01', procedure_type: 'SYNTHETIC-Procedure-1' },
      ], 1, 1, 1));
    });

    expect(result.current.appointments).toEqual([{ id: 22, appointment_date: '2026-01-02' }]);
    expect(result.current.skinExaminations).toEqual([
      { id: 22, examination_date: '2026-01-02', diagnosis: 'SYNTHETIC-Diagnosis-2' },
    ]);
    expect(result.current.cosmeticProcedures).toEqual([
      { id: 23, procedure_date: '2026-01-02', procedure_type: 'SYNTHETIC-Procedure-2' },
    ]);
  });
});
