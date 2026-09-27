import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../client';
import { buildProcedureEmrPayload, saveCosmeticProcedureToEmr } from '../dermaProcedures';

vi.mock('../client', () => ({ api: { get: vi.fn(), post: vi.fn() } }));

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);

function response(data: unknown) {
  return { data, status: 200 } as never;
}

function httpError(status: number) {
  return { response: { status } } as never;
}

const ENTRY = {
  procedure_date: '2026-09-27',
  procedure_type: 'SYNTHETIC procedure',
  area_treated: 'SYNTHETIC area',
  products_used: 'SYNTHETIC product',
  results: 'SYNTHETIC result',
  follow_up: 'SYNTHETIC follow up',
  recorded_at: '2026-09-27T10:00:00.000Z',
};

describe('saveCosmeticProcedureToEmr (P2-4b)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('appends the procedure to the existing visit EMR with optimistic locking', async () => {
    mockedGet.mockResolvedValue(response({
      id: 7,
      row_version: 3,
      data: {
        specialty: 'dermatology',
        complaints: 'existing complaints',
        specialty_data: {
          skin_type: 'dry',
          procedures: [{ procedure_type: 'earlier procedure', procedure_date: '2026-09-01' }],
        },
      },
    }));
    mockedPost.mockResolvedValue(response({ id: 7 }));

    await saveCosmeticProcedureToEmr(55, ENTRY);

    expect(mockedGet).toHaveBeenCalledWith('/v2/emr/55');
    expect(mockedPost).toHaveBeenCalledTimes(1);
    const [url, payload] = mockedPost.mock.calls[0];
    expect(url).toBe('/v2/emr/55');
    expect(payload).toMatchObject({
      row_version: 3,
      is_draft: true,
    });
    const data = (payload as { data: Record<string, unknown> }).data;
    expect(data.specialty).toBe('dermatology');
    expect(data.complaints).toBe('existing complaints');
    const specialtyData = data.specialty_data as Record<string, unknown>;
    const procedures = specialtyData.procedures as unknown[];
    expect(procedures).toHaveLength(2);
    expect(procedures[0]).toMatchObject({ procedure_type: 'earlier procedure' });
    expect(procedures[1]).toMatchObject({ procedure_type: 'SYNTHETIC procedure', recorded_at: ENTRY.recorded_at });
  });

  it('creates a fresh dermatology EMR when the visit has none (404)', async () => {
    mockedGet.mockRejectedValue(httpError(404));
    mockedPost.mockResolvedValue(response({ id: 8 }));

    await saveCosmeticProcedureToEmr(56, ENTRY);

    const [, payload] = mockedPost.mock.calls[0];
    expect(payload).toMatchObject({ row_version: 0, is_draft: true });
    const data = (payload as { data: Record<string, unknown> }).data;
    expect(data.specialty).toBe('dermatology');
    expect(data.complaints).toBe('');
    const specialtyData = data.specialty_data as Record<string, unknown>;
    expect(specialtyData.procedures).toHaveLength(1);
    expect((specialtyData.procedures as unknown[])[0]).toMatchObject({ procedure_type: 'SYNTHETIC procedure' });
  });

  it('retries once on 409 with a freshly read row_version', async () => {
    mockedGet
      .mockResolvedValueOnce(response({ row_version: 3, data: { specialty: 'dermatology', specialty_data: {} } }))
      .mockResolvedValueOnce(response({ row_version: 4, data: { specialty: 'dermatology', specialty_data: {} } }));
    mockedPost
      .mockRejectedValueOnce(httpError(409))
      .mockResolvedValueOnce(response({ id: 9 }));

    await saveCosmeticProcedureToEmr(57, ENTRY);

    expect(mockedGet).toHaveBeenCalledTimes(2);
    expect(mockedPost).toHaveBeenCalledTimes(2);
    expect((mockedPost.mock.calls[0][1] as { row_version: number }).row_version).toBe(3);
    expect((mockedPost.mock.calls[1][1] as { row_version: number }).row_version).toBe(4);
  });

  it('does not retry non-conflict save errors and surfaces them', async () => {
    mockedGet.mockResolvedValue(response({ row_version: 1, data: { specialty: 'dermatology', specialty_data: {} } }));
    mockedPost.mockRejectedValue(httpError(500));

    await expect(saveCosmeticProcedureToEmr(58, ENTRY)).rejects.toBeTruthy();

    expect(mockedPost).toHaveBeenCalledTimes(1);
  });

  it('re-throws read errors other than 404 without saving', async () => {
    mockedGet.mockRejectedValue(httpError(500));

    await expect(saveCosmeticProcedureToEmr(59, ENTRY)).rejects.toBeTruthy();

    expect(mockedPost).not.toHaveBeenCalled();
  });

  it('keeps non-array procedures payloads from corrupting the append', () => {
    const payload = buildProcedureEmrPayload(
      { row_version: 2, data: { specialty: 'dermatology', specialty_data: { procedures: 'junk' } } } as never,
      ENTRY,
    );
    const specialtyData = (payload.data as Record<string, unknown>).specialty_data as Record<string, unknown>;
    expect(specialtyData.procedures).toEqual([ENTRY]);
  });
});
