// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

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

describe('queue API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads public queue profiles', async () => {
    api.get.mockResolvedValueOnce({ data: { items: [] } });
    const data = await fetchPublicQueueProfiles();

    expect(api.get).toHaveBeenCalledWith('/queues/profiles/public');
    expect(data).toEqual({ items: [] });
  });

  it('loads QR token info by token', async () => {
    api.get.mockResolvedValueOnce({ data: { valid: true } });
    const data = await fetchQrTokenInfo('token-123');

    expect(api.get).toHaveBeenCalledWith('/queue/qr-tokens/token-123/info');
    expect(data).toEqual({ valid: true });
  });

  it('starts queue join session', async () => {
    api.post.mockResolvedValueOnce({ data: { started: true } });
    const data = await startQueueJoinSession('token-abc');

    expect(api.post).toHaveBeenCalledWith('/queue/join/start', { token: 'token-abc' });
    expect(data).toEqual({ started: true });
  });

  it('completes queue join session', async () => {
    const payload = { token: 'token-abc', patient_name: 'Test User' };
    api.post.mockResolvedValueOnce({ data: { success: true } });
    const data = await completeQueueJoinSession(payload);

    expect(api.post).toHaveBeenCalledWith('/queue/join/complete', payload);
    expect(data).toEqual({ success: true });
  });

  it('posts registrar edit deltas without create-like queue endpoints', async () => {
    api.post.mockResolvedValueOnce({ data: { success: true, total_amount: 25000 } });

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

    expect(api.post).toHaveBeenCalledWith('/registrar/cart/edit-delta', {
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
