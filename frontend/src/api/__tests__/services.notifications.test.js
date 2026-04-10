import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiRequestMock = vi.hoisted(() => vi.fn());

vi.mock('../client.js', () => ({
  apiRequest: apiRequestMock,
  api: {}
}));

import { apiRequest } from '../client.js';
import {
  clearNotificationQueryCache,
  notificationsService
} from '../services.js';

describe('notificationsService cache', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearNotificationQueryCache();
  });

  it('deduplicates identical inbox requests while the cache is warm', async () => {
    apiRequest.mockResolvedValueOnce({ items: [{ id: 1 }] });

    const params = { role: 'admin', recipient_id: 45, recipient_type: 'admin', status: 'all', limit: 50 };
    const first = await notificationsService.getInbox(params);
    const second = await notificationsService.getInbox(params);

    expect(first).toEqual({ items: [{ id: 1 }] });
    expect(second).toEqual({ items: [{ id: 1 }] });
    expect(apiRequest).toHaveBeenCalledTimes(1);
    expect(apiRequest).toHaveBeenCalledWith(
      'GET',
      '/notifications/inbox?role=admin&recipient_id=45&recipient_type=admin&status=all&limit=50'
    );
  });

  it('invalidates cached inbox data after a mutation', async () => {
    apiRequest.mockResolvedValue({ ok: true });

    const params = { role: 'admin', recipient_id: 45, recipient_type: 'admin', status: 'all', limit: 50 };

    await notificationsService.getInbox(params);
    await notificationsService.markAsRead('delivery-1');
    await notificationsService.getInbox(params);

    expect(apiRequest).toHaveBeenCalledTimes(3);
  });
});
