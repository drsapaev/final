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

// The mock replaces `api` at runtime; cast it through unknown so we can
// call vitest mock methods (mockImplementationOnce / mockResolvedValueOnce)
// without fighting the real AxiosInstance type.
const apiMockTyped = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

type ResolveFn = (value: unknown) => void;

describe('messages service cache', () => {
  beforeEach(() => {
    clearMessageQueryCache();
    vi.clearAllMocks();
  });

  it('deduplicates concurrent conversation requests and reuses fresh cache', async () => {
    let resolveRequest: ResolveFn | undefined;
    apiMockTyped.get.mockImplementationOnce(() => new Promise((resolve) => {
      resolveRequest = resolve as ResolveFn;
    }));

    const first = getConversations();
    const second = getConversations();

    expect(apiMockTyped.get).toHaveBeenCalledTimes(1);

    resolveRequest?.({ data: { conversations: [{ id: 1 }], total_unread: 2 } });

    await expect(first).resolves.toEqual({ conversations: [{ id: 1 }], total_unread: 2 });
    await expect(second).resolves.toEqual({ conversations: [{ id: 1 }], total_unread: 2 });

    const cached = await getConversations();
    expect(cached).toEqual({ conversations: [{ id: 1 }], total_unread: 2 });
    expect(apiMockTyped.get).toHaveBeenCalledTimes(1);
  });

  it('deduplicates unread count requests and clears cache after sending a message', async () => {
    let resolveUnread: ResolveFn | undefined;
    apiMockTyped.get.mockImplementationOnce(() => new Promise((resolve) => {
      resolveUnread = resolve as ResolveFn;
    }));

    const unreadFirst = getUnreadCount();
    const unreadSecond = getUnreadCount();

    expect(apiMockTyped.get).toHaveBeenCalledTimes(1);

    resolveUnread?.({ data: { unread_count: 4 } });

    await expect(unreadFirst).resolves.toBe(4);
    await expect(unreadSecond).resolves.toBe(4);

    apiMockTyped.post.mockResolvedValueOnce({ data: { id: 9, content: 'ok' } });
    await sendMessage(2, 'Hello');

    apiMockTyped.get.mockResolvedValueOnce({ data: { unread_count: 1 } });
    await expect(getUnreadCount()).resolves.toBe(1);
    expect(apiMockTyped.get).toHaveBeenCalledTimes(2);
  });
});
