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
  startQueueJoinSession,
} from '../queue';

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
        { service_id: '7', quantity: '2', specialist_id: null },
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
      services: [
        { service_id: 7, quantity: 2, specialist_id: null },
        { service_id: 8, quantity: 1, specialist_id: 3 },
      ],
      existing_queue_entry_ids: [10, 11],
    });
    expect(data).toEqual({ success: true, total_amount: 25000 });
  });
});
