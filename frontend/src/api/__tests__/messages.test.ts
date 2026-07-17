// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiMock } = vi.hoisted(() => {
  const apiMock = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  };

  return { apiMock };
});

vi.mock('../client', () => ({
  api: apiMock,
}));

import { api } from '../client';
import {
  clearMessageQueryCache,
  getConversations,
  getUnreadCount,
  sendMessage,
} from '../messages';

describe('messages service cache', () => {
  beforeEach(() => {
    clearMessageQueryCache();
    vi.clearAllMocks();
  });

  it('deduplicates concurrent conversation requests and reuses fresh cache', async () => {
    let resolveRequest;
    api.get.mockImplementationOnce(() => new Promise((resolve) => {
      resolveRequest = resolve;
    }));

    const first = getConversations();
    const second = getConversations();

    expect(api.get).toHaveBeenCalledTimes(1);

    resolveRequest?.({ data: { conversations: [{ id: 1 }], total_unread: 2 } });

    await expect(first).resolves.toEqual({ conversations: [{ id: 1 }], total_unread: 2 });
    await expect(second).resolves.toEqual({ conversations: [{ id: 1 }], total_unread: 2 });

    const cached = await getConversations();
    expect(cached).toEqual({ conversations: [{ id: 1 }], total_unread: 2 });
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it('deduplicates unread count requests and clears cache after sending a message', async () => {
    let resolveUnread;
    api.get.mockImplementationOnce(() => new Promise((resolve) => {
      resolveUnread = resolve;
    }));

    const unreadFirst = getUnreadCount();
    const unreadSecond = getUnreadCount();

    expect(api.get).toHaveBeenCalledTimes(1);

    resolveUnread?.({ data: { unread_count: 4 } });

    await expect(unreadFirst).resolves.toBe(4);
    await expect(unreadSecond).resolves.toBe(4);

    api.post.mockResolvedValueOnce({ data: { id: 9, content: 'ok' } });
    await sendMessage(2, 'Hello');

    api.get.mockResolvedValueOnce({ data: { unread_count: 1 } });
    await expect(getUnreadCount()).resolves.toBe(1);
    expect(api.get).toHaveBeenCalledTimes(2);
  });
});
