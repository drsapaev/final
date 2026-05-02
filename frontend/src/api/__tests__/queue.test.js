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
});
