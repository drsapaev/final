import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiRequestMock = vi.hoisted(() => vi.fn());

vi.mock('../client', () => ({
  apiRequest: apiRequestMock,
  api: {}
}));

import { apiRequest } from '../client';
import {
  clearNotificationQueryCache,
  notificationsService
} from '../services';

// Cast the apiRequest (mocked at runtime) so we can call vitest mock
// methods on it without fighting the real apiRequest signature.
const apiRequestMockTyped = apiRequest as unknown as ReturnType<typeof vi.fn>;

describe('notificationsService cache', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearNotificationQueryCache();
  });

  it('deduplicates identical inbox requests while the cache is warm', async () => {
    apiRequestMockTyped.mockResolvedValueOnce({ items: [{ id: 1 }] });

    const params = { role: 'admin', recipient_id: 45, recipient_type: 'admin', status: 'all', limit: 50 };
    const first = await notificationsService.getInbox(params);
    const second = await notificationsService.getInbox(params);

    expect(first).toEqual({ items: [{ id: 1 }] });
    expect(second).toEqual({ items: [{ id: 1 }] });
    expect(apiRequestMockTyped).toHaveBeenCalledTimes(1);
    expect(apiRequestMockTyped).toHaveBeenCalledWith(
      'GET',
      '/notifications/inbox?role=admin&recipient_id=45&recipient_type=admin&status=all&limit=50'
    );
  });

  it('invalidates cached inbox data after a mutation', async () => {
    apiRequestMockTyped.mockResolvedValue({ ok: true });

    const params = { role: 'admin', recipient_id: 45, recipient_type: 'admin', status: 'all', limit: 50 };

    await notificationsService.getInbox(params);
    await notificationsService.markAsRead('delivery-1');
    await notificationsService.getInbox(params);

    expect(apiRequestMockTyped).toHaveBeenCalledTimes(3);
  });

  it('supports canonical settings and policy endpoints', async () => {
    apiRequestMockTyped
      .mockResolvedValueOnce({ email_appointment_reminder: true })
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ policy: { dnd: { enabled: true } } })
      .mockResolvedValueOnce({ ok: true });

    const userId = 20;
    const settingsPayload = { email_appointment_reminder: false };
    const policyPayload = { dnd: { enabled: true, always_on: false, start: '22:00', end: '07:00' } };

    await expect(notificationsService.getSettings(userId)).resolves.toEqual({
      email_appointment_reminder: true
    });
    await expect(notificationsService.updateSettings(userId, settingsPayload)).resolves.toEqual({ ok: true });
    await expect(notificationsService.getPolicy(userId)).resolves.toEqual({
      policy: { dnd: { enabled: true } }
    });
    await expect(notificationsService.updatePolicy(userId, policyPayload)).resolves.toEqual({ ok: true });

    expect(apiRequestMockTyped).toHaveBeenNthCalledWith(1, 'GET', '/notifications/settings/20');
    expect(apiRequestMockTyped).toHaveBeenNthCalledWith(2, 'PUT', '/notifications/settings/20', {
      data: settingsPayload
    });
    expect(apiRequestMockTyped).toHaveBeenNthCalledWith(3, 'GET', '/notifications/settings/20/policy');
    expect(apiRequestMockTyped).toHaveBeenNthCalledWith(4, 'PUT', '/notifications/settings/20/policy', {
      data: policyPayload
    });
  });
});
