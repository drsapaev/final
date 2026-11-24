import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import useAIChat from '../useAIChat';

const { apiMock, tokenManagerMock, loggerMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
  tokenManagerMock: { getAccessToken: vi.fn(() => 'synthetic-access') },
  loggerMock: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

vi.mock('../../api/client', () => ({ api: apiMock }));
vi.mock('../../api/runtime', () => ({ buildWsUrl: (path: string) => `ws://localhost${path}` }));
vi.mock('../../utils/logger', () => ({ default: loggerMock }));
vi.mock('../../utils/tokenManager', () => ({ tokenManager: tokenManagerMock }));

const safeMeta = { requires_doctor_confirmation: true };
const unsafeMarkers = [
  undefined,
  null,
  false,
  1,
  'true',
  {},
  [],
  { requires_doctor_confirmation: false },
  { requires_doctor_confirmation: 1 },
  { requires_doctor_confirmation: 'true' },
  { requires_doctor_confirmation: null },
] as const;

function marked(role: string, content: string, ...marker: [unknown?]) {
  return {
    id: `${role}-${content}`,
    role,
    content,
    ai_safety_meta: marker.length ? marker[0] : safeMeta,
  };
}

function setupHistory(sessionId: number, history: unknown[]) {
  apiMock.get.mockImplementation((url: string) => {
    if (url === `/ai/chat/sessions/${sessionId}`) return Promise.resolve({ data: { id: sessionId } });
    if (url === `/ai/chat/sessions/${sessionId}/messages`) return Promise.resolve({ data: history });
    throw new Error(`Unexpected GET ${url}`);
  });
}

class FakeSocket {
  static OPEN = 1;
  static instances: FakeSocket[] = [];
  readyState = FakeSocket.OPEN;
  onopen: (() => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => { this.readyState = 3; });

  constructor(_url: string, _protocols?: string[]) {
    FakeSocket.instances.push(this);
  }

  message(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

describe('useAIChat medical safety', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('accepts marked assistant history and preserves ordinary user messages', async () => {
    const history = [{ id: 'user-1', role: 'user', content: 'question' }, marked('assistant', 'safe')];
    setupHistory(7, history);
    const { result } = renderHook(() => useAIChat());
    await act(async () => { await result.current.loadSession(7); });
    expect(result.current.messages).toEqual(history);
    expect(result.current.error).toBeNull();
  });

  it.each(unsafeMarkers.map(marker => [marker]))('hides every AI history message when the marker is invalid: %s', async (marker) => {
    const user = marked('user', 'question', null);
    setupHistory(7, [user, marked('assistant', 'unsafe', marker), marked('assistant', 'otherwise-safe')]);
    const { result } = renderHook(() => useAIChat());
    await act(async () => { await result.current.loadSession(7); });
    expect(result.current.messages).toEqual([user]);
    expect(result.current.error).toBeTruthy();
    expect(JSON.stringify(result.current.messages)).not.toContain('unsafe');
    expect(JSON.stringify(loggerMock.error.mock.calls)).not.toContain('unsafe');
  });

  it.each(['system', 'unknown-role'])('does not show untrusted %s history as an AI answer', async (role) => {
    const user = marked('user', 'question', null);
    setupHistory(7, [user, marked(role, 'untrusted', null)]);
    const { result } = renderHook(() => useAIChat());
    await act(async () => { await result.current.loadSession(7); });
    expect(result.current.messages).toEqual([user]);
    expect(result.current.error).toBeTruthy();
  });

  it('rejects an unknown history role even when it carries a valid marker', async () => {
    const user = marked('user', 'question', null);
    setupHistory(7, [user, marked('unknown-role', 'untrusted')]);
    const { result } = renderHook(() => useAIChat());
    await act(async () => { await result.current.loadSession(7); });
    expect(result.current.messages).toEqual([user]);
    expect(result.current.error).toBeTruthy();
  });

  it.each(unsafeMarkers.map(marker => [marker]))('rejects an unmarked or malformed HTTP assistant response: %s', async (marker) => {
    apiMock.post.mockImplementation((url: string) => url === '/ai/chat/sessions'
      ? Promise.resolve({ data: { id: 7 } })
      : Promise.resolve({ data: marked('assistant', 'unsafe-reply', marker) }));
    const { result } = renderHook(() => useAIChat());
    let response: unknown;
    await act(async () => { response = await result.current.sendMessage('question'); });
    expect(response).toBeNull();
    expect(result.current.error).toBeTruthy();
    expect(JSON.stringify(result.current.messages)).not.toContain('unsafe-reply');
    expect(result.current.messages.some(message => message._pending)).toBe(false);
    expect(JSON.stringify(loggerMock.error.mock.calls)).not.toContain('unsafe-reply');
  });

  it('accepts a strictly marked HTTP assistant response', async () => {
    const safeReply = marked('assistant', 'safe-reply');
    apiMock.post.mockImplementation((url: string) => url === '/ai/chat/sessions'
      ? Promise.resolve({ data: { id: 7 } }) : Promise.resolve({ data: safeReply }));
    const { result } = renderHook(() => useAIChat());
    let response: unknown;
    await act(async () => { response = await result.current.sendMessage('question'); });
    expect(response).toEqual(safeReply);
    expect(result.current.messages.map(message => message.role)).toEqual(['user', 'assistant']);
    expect(result.current.messages[1]).toEqual(safeReply);
    expect(result.current.error).toBeNull();
  });

  it('rejects a marked non-assistant HTTP response', async () => {
    apiMock.post.mockImplementation((url: string) => url === '/ai/chat/sessions'
      ? Promise.resolve({ data: { id: 7 } })
      : Promise.resolve({ data: marked('user', 'spoofed') }));
    const { result } = renderHook(() => useAIChat());
    let response: unknown;
    await act(async () => { response = await result.current.sendMessage('question'); });
    expect(response).toBeNull();
    expect(JSON.stringify(result.current.messages)).not.toContain('spoofed');
  });

  it('does not display a delayed unsafe response after switching sessions', async () => {
    let resolveResponse!: (value: unknown) => void;
    const delayed = new Promise(resolve => { resolveResponse = resolve; });
    apiMock.post.mockImplementation((url: string) => url === '/ai/chat/sessions'
      ? Promise.resolve({ data: { id: 7 } }) : delayed);
    setupHistory(8, [marked('user', 'other-session', null)]);
    const { result } = renderHook(() => useAIChat());
    let pending!: Promise<unknown>;
    await act(async () => { pending = result.current.sendMessage('question'); });
    await waitFor(() => expect(apiMock.post).toHaveBeenCalledTimes(2));
    await act(async () => { await result.current.loadSession(8); });
    let response: unknown;
    await act(async () => { resolveResponse({ data: marked('assistant', 'late-unsafe', null) }); response = await pending; });
    expect(response).toBeNull();
    expect(result.current.currentSession?.id).toBe(8);
    expect(result.current.messages).toEqual([marked('user', 'other-session', null)]);
    expect(result.current.error).toBeNull();
  });

  it('renders and completes a strictly marked multi-chunk WebSocket answer', () => {
    const { result } = renderHook(() => useAIChat({ useWebSocket: true }));
    const socket = FakeSocket.instances[0];
    act(() => {
      socket.onopen?.();
      socket.message({ type: 'chunk', content: 'safe ', ai_safety_meta: safeMeta });
      socket.message({ type: 'chunk', content: 'answer', ai_safety_meta: safeMeta });
      socket.message({ type: 'done', message_id: 42, ai_safety_meta: safeMeta });
    });
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({ role: 'assistant', content: 'safe answer', id: 42, _streaming: false });
    expect(result.current.streaming).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it.each(unsafeMarkers.map(marker => [marker]))('blocks an unsafe WebSocket chunk and all later frames: %s', (marker) => {
    const { result } = renderHook(() => useAIChat({ useWebSocket: true }));
    const socket = FakeSocket.instances[0];
    act(() => {
      socket.onopen?.();
      socket.message({ type: 'chunk', content: 'unsafe-reply', ai_safety_meta: marker });
      socket.message({ type: 'chunk', content: 'late-reply', ai_safety_meta: safeMeta });
      socket.message({ type: 'done', ai_safety_meta: safeMeta });
    });
    expect(result.current.messages).toEqual([]);
    expect(result.current.error).toBeTruthy();
    expect(socket.close).toHaveBeenCalled();
    expect(JSON.stringify(loggerMock.error.mock.calls)).not.toContain('unsafe-reply');
  });

  it('removes an earlier valid partial and blocks later frames when done lacks safety metadata', () => {
    const { result } = renderHook(() => useAIChat({ useWebSocket: true }));
    const socket = FakeSocket.instances[0];
    act(() => { socket.onopen?.(); socket.message({ type: 'chunk', content: 'partial', ai_safety_meta: safeMeta }); });
    expect(result.current.messages.some(message => message.content === 'partial')).toBe(true);
    act(() => {
      socket.message({ type: 'done' });
      socket.message({ type: 'chunk', content: 'late', ai_safety_meta: safeMeta });
    });
    expect(result.current.messages).toEqual([]);
    expect(result.current.streaming).toBe(false);
    expect(result.current.error).toBeTruthy();
    expect(socket.close).toHaveBeenCalled();
  });

  it('clears a partial response and returns to idle when the socket closes with 1011', () => {
    const { result } = renderHook(() => useAIChat({ useWebSocket: true }));
    const socket = FakeSocket.instances[0];
    act(() => { socket.onopen?.(); socket.message({ type: 'chunk', content: 'partial', ai_safety_meta: safeMeta }); });
    expect(result.current.messages.some(message => message.content === 'partial')).toBe(true);
    act(() => socket.onclose?.({ code: 1011, reason: 'temporary failure' }));
    expect(result.current.messages.some(message => message.content === 'partial')).toBe(false);
    expect(result.current.streaming).toBe(false);
    expect(result.current.sessionState.streamStatus).toBe('idle');
  });

  it('clears a partial response on an explicit user disconnect', () => {
    const { result } = renderHook(() => useAIChat({ useWebSocket: true }));
    const socket = FakeSocket.instances[0];
    act(() => { socket.onopen?.(); socket.message({ type: 'chunk', content: 'partial', ai_safety_meta: safeMeta }); });
    expect(result.current.messages.some(message => message.content === 'partial')).toBe(true);
    act(() => result.current.disconnectWebSocket());
    expect(result.current.messages.some(message => message.content === 'partial')).toBe(false);
    expect(result.current.streaming).toBe(false);
    expect(result.current.sessionState.streamStatus).toBe('idle');
    expect(socket.close).toHaveBeenCalled();
  });

  it('closes a replaced socket and discards its incomplete stream', () => {
    const { result } = renderHook(() => useAIChat({ useWebSocket: true }));
    const first = FakeSocket.instances[0];
    act(() => { first.onopen?.(); first.message({ type: 'chunk', content: 'old-partial', ai_safety_meta: safeMeta }); });
    act(() => result.current.connectWebSocket());
    expect(first.close).toHaveBeenCalled();
    expect(result.current.messages.some(message => message.content === 'old-partial')).toBe(false);
    expect(result.current.streaming).toBe(false);
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it('ignores a late frame from a replaced socket', () => {
    const { result } = renderHook(() => useAIChat({ useWebSocket: true }));
    const first = FakeSocket.instances[0];
    const staleHandler = first.onmessage;
    act(() => { first.onopen?.(); result.current.connectWebSocket(); });
    act(() => staleHandler?.({ data: JSON.stringify({ type: 'chunk', content: 'late', ai_safety_meta: safeMeta }) }));
    expect(result.current.messages).toEqual([]);
  });

  it('stops reconnecting after a safety metadata close', () => {
    vi.useFakeTimers();
    const { result, unmount } = renderHook(() => useAIChat({ useWebSocket: true }));
    const first = FakeSocket.instances[0];
    act(() => { first.onopen?.(); first.onclose?.({ code: 1011, reason: 'Safety metadata required' }); });
    act(() => vi.advanceTimersByTime(120_000));
    expect(FakeSocket.instances).toHaveLength(1);
    expect(result.current.connected).toBe(false);
    expect(result.current.error).toBeTruthy();
    unmount();
    vi.useRealTimers();
  });

  it('bounds retries when a server repeatedly opens and closes without a valid frame', () => {
    vi.useFakeTimers();
    const { unmount } = renderHook(() => useAIChat({ useWebSocket: true }));
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const socket = FakeSocket.instances[attempt];
      expect(socket).toBeDefined();
      act(() => { socket.onopen?.(); socket.onclose?.({ code: 1006, reason: '' }); });
      act(() => vi.advanceTimersByTime(20_000));
    }
    expect(FakeSocket.instances).toHaveLength(6);
    act(() => vi.advanceTimersByTime(120_000));
    expect(FakeSocket.instances).toHaveLength(6);
    unmount();
    vi.useRealTimers();
  });
});
