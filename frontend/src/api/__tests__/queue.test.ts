import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

import { api } from '../client';
import {
  applyRegistrarEditDelta,
  completeQueueJoinSession,
  fetchPublicQueueProfiles,
  fetchQrTokenInfo,
  fetchQueuesToday,
  startQueueJoinSession,
} from '../queue';
import { mapQueuePayloadDto } from '../mappers/queue';

// Cast api through unknown so we can call vitest mock methods on its
// members without fighting the real AxiosInstance type.
const apiMock = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
};

describe('queue API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads public queue profiles', async () => {
    apiMock.get.mockResolvedValueOnce({ data: { items: [] } });
    const data = await fetchPublicQueueProfiles();

    expect(apiMock.get).toHaveBeenCalledWith('/queues/profiles/public');
    expect(data).toEqual({ items: [] });
  });

  it('loads QR token info by token', async () => {
    apiMock.get.mockResolvedValueOnce({ data: { valid: true } });
    const data = await fetchQrTokenInfo('token-123');

    expect(apiMock.get).toHaveBeenCalledWith('/queue/qr-tokens/token-123/info');
    expect(data).toEqual({ valid: true });
  });

  it('starts queue join session', async () => {
    apiMock.post.mockResolvedValueOnce({ data: { started: true } });
    const data = await startQueueJoinSession('token-abc');

    expect(apiMock.post).toHaveBeenCalledWith('/queue/join/start', { token: 'token-abc' });
    expect(data).toEqual({ started: true });
  });

  it('completes queue join session', async () => {
    const payload = { token: 'token-abc', patient_name: 'Test User' };
    apiMock.post.mockResolvedValueOnce({ data: { success: true } });
    const data = await completeQueueJoinSession(payload);

    expect(apiMock.post).toHaveBeenCalledWith('/queue/join/complete', payload);
    expect(data).toEqual({ success: true });
  });

  it('posts registrar edit deltas without create-like queue endpoints', async () => {
    apiMock.post.mockResolvedValueOnce({ data: { success: true, total_amount: 25000 } });

    const data = await applyRegistrarEditDelta({
      patientId: '42',
      targetDate: '2026-05-31',
      patientData: { full_name: 'Test Patient', sex: 'F' },
      services: [
        { service_id: '7', quantity: '2', specialist_id: null, queue_entry_id: 777 },
        { service_id: 8, quantity: 1, specialist_id: '3' },
      ],
      existingQueueEntryIds: ['10', 11],
    });

    expect(apiMock.post).toHaveBeenCalledWith('/registrar/cart/edit-delta', {
      patient_id: 42,
      target_date: '2026-05-31',
      patient_data: { full_name: 'Test Patient', sex: 'F' },
      payment_method: 'cash',
      discount_mode: 'none',
      all_free: false,
      // Codex R10 PR 3115 (P1): queue_entry_id (идентичность исходной записи
      // позиции) доходит до API; отсутствие — явный null (глобальный контракт).
      services: [
        { service_id: 7, quantity: 2, specialist_id: null, queue_entry_id: 777 },
        { service_id: 8, quantity: 1, specialist_id: 3, queue_entry_id: null },
      ],
      existing_queue_entry_ids: [10, 11],
    });
    expect(data).toEqual({ success: true, total_amount: 25000 });
  });
});

// REG-FE-034 (registrar audit ledger 3803): канонический конверт ответа
// /registrar/queues/today — объект с МАССИВОМ queues. Всё остальное
// (null, чужой конверт, отсутствие queues) — ошибка контракта, а не
// «пустая очередь»: замалчивание превращает регрессию API/прокси в
// «сегодня записей нет».
describe('queue API envelope fail-closed (REG-FE-034)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('mapQueuePayloadDto rejects null and non-object payloads instead of inventing an empty queue', () => {
    expect(() => mapQueuePayloadDto(null as never)).toThrow();
    expect(() => mapQueuePayloadDto(undefined as never)).toThrow();
    expect(() => mapQueuePayloadDto('nope' as never)).toThrow();
  });

  it('mapQueuePayloadDto rejects objects without a queues array', () => {
    expect(() => mapQueuePayloadDto({ message: 'temporary issue' } as never)).toThrow();
    expect(() => mapQueuePayloadDto({ queues: null } as never)).toThrow();
    expect(() => mapQueuePayloadDto({ other: [] } as never)).toThrow();
  });

  it('mapQueuePayloadDto passes a valid envelope through', () => {
    const payload = { queues: [] } as never;
    expect(mapQueuePayloadDto(payload)).toEqual({ queues: [] });
  });

  it('fetchQueuesToday rejects a malformed 200 body', async () => {
    apiMock.get.mockResolvedValueOnce({ data: { message: 'unexpected envelope' } });
    await expect(fetchQueuesToday('2026-11-03')).rejects.toThrow();
    expect(apiMock.get).toHaveBeenCalledWith(
      '/registrar/queues/today',
      expect.objectContaining({ params: { target_date: '2026-11-03' } }),
    );
  });

  it('fetchQueuesToday rejects a null body', async () => {
    apiMock.get.mockResolvedValueOnce({ data: null });
    await expect(fetchQueuesToday('2026-11-03')).rejects.toThrow();
  });

  it('fetchQueuesToday resolves a valid empty envelope', async () => {
    apiMock.get.mockResolvedValueOnce({ data: { queues: [] } });
    await expect(fetchQueuesToday('2026-11-03')).resolves.toEqual({ queues: [] });
  });
});
