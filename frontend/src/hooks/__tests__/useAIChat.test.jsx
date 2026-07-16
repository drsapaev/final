import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import useAIChat from '../useAIChat';

const {
  apiMock,
  loggerMock,
  runtimeMock,
  tokenManagerMock,
} = vi.hoisted(() => {
  const apiMock = {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  };

  const loggerMock = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  };

  const runtimeMock = {
    buildWsUrl: vi.fn((path) => `ws://localhost:18000${path}`),
  };

  const tokenManagerMock = {
    getAccessToken: vi.fn(() => 'token-1'),
    isTokenValid: vi.fn(() => true),
  };

  return {
    apiMock,
    loggerMock,
    runtimeMock,
    tokenManagerMock,
  };
});

vi.mock('../../api/client', () => ({
  api: apiMock,
}));

vi.mock('../../api/runtime', () => ({
  buildWsUrl: runtimeMock.buildWsUrl,
}));

vi.mock('../../utils/logger', () => ({
  default: loggerMock,
}));

vi.mock('../../utils/tokenManager', () => ({
  tokenManager: tokenManagerMock,
}));

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}

function makeSessionResponse(id, messageCount = 1) {
  const stamp = `2026-03-29T10:0${id}:00Z`;
  return {
    data: {
      id,
      title: `Session ${id}`,
      context_type: 'general',
      specialty: 'general',
      is_active: true,
      message_count: messageCount,
      created_at: stamp,
      updated_at: stamp,
    },
  };
}

describe('useAIChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('keeps the newest session when a stale loadSession request resolves later', async () => {
    const session1 = deferred();
    const session2 = deferred();
    const session2Messages = deferred();

    apiMock.get.mockImplementation((url) => {
      if (url === '/ai/chat/sessions/1') return session1.promise;
      if (url === '/ai/chat/sessions/1/messages') {
        throw new Error('stale loadSession should not request messages for session 1');
      }
      if (url === '/ai/chat/sessions/2') return session2.promise;
      if (url === '/ai/chat/sessions/2/messages') return session2Messages.promise;

      throw new Error(`Unexpected GET ${url}`);
    });

    const { result } = renderHook(() => useAIChat({ contextType: 'general', specialty: 'general' }));

    let loadSession1;
    let loadSession2;
    await act(async () => {
      loadSession1 = result.current.loadSession(1);
      loadSession2 = result.current.loadSession(2);
    });

    session2.resolve(makeSessionResponse(2));
    await waitFor(() => {
      expect(apiMock.get).toHaveBeenCalledWith('/ai/chat/sessions/2/messages');
    });

    session2Messages.resolve({
      data: [
        {
          id: 22,
          role: 'assistant',
          content: 'Ответ для второй сессии',
          created_at: '2026-03-29T10:02:10Z',
        },
      ],
    });

    session1.resolve(makeSessionResponse(1));

    await act(async () => {
      await Promise.allSettled([loadSession1, loadSession2]);
    });

    await waitFor(() => {
      expect(result.current.currentSession?.id).toBe(2);
      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]).toMatchObject({
        id: 22,
        role: 'assistant',
        content: 'Ответ для второй сессии',
      });
    });

    expect(apiMock.get).not.toHaveBeenCalledWith('/ai/chat/sessions/1/messages');
    expect(loggerMock.error).not.toHaveBeenCalled();
  });
});
