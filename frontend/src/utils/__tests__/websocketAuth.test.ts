/**
 * WSHELPER-FE-001 / WSHELPER-FE-002: contract tests for the generic
 * authenticated WebSocket helper.
 *
 * WSHELPER-FE-001 (helper half): `createQueueWebSocket` targets the legacy
 * optional-auth endpoint with the JWT in the `bearer.<token>` SUBPROTOCOL
 * and department/date only in the query — the backend half (echoing
 * accept + canonical token resolution) is covered by
 * `backend/tests/integration/test_legacy_ws_queue_auth_endpoints.py`.
 *
 * WSHELPER-FE-002: `onMessage` receives the RAW `MessageEvent` (the
 * declared contract) and server `ping` frames are answered with `pong`
 * automatically, so heartbeat/reconnect wrappers can parse `event.data`
 * and idle connections stay alive.
 *
 * Synthetic fixtures only: a stubbed global WebSocket, no network, no
 * real JWT, no patient data.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/runtime', () => ({
  buildWsUrl: vi.fn((path: string) => `ws://synthetic.test${path}`),
}));

vi.mock('../logger', () => ({
  default: { log: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

vi.mock('../tokenManager', () => ({
  tokenManager: { getAccessToken: vi.fn(() => 'synthetic-jwt') },
}));

import { createQueueWebSocket } from '../websocketAuth';

class FakeMessageEvent {
  constructor(public data: string) {}
}

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  subprotocols: string[];
  sent: string[] = [];
  onopen: ((event: unknown) => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;

  constructor(url: string, subprotocols?: string[]) {
    this.url = url;
    this.subprotocols = subprotocols ?? [];
    FakeWebSocket.instances.push(this);
  }

  send(payload: string): void {
    this.sent.push(payload);
  }
}

describe('websocketAuth helper contract (WSHELPER-FE-001/002)', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('targets the legacy optional-auth route with subprotocol token and query-only department/date', () => {
    const ws = createQueueWebSocket('specialist_7', '2026-11-12') as unknown as FakeWebSocket;

    expect(ws.url).toBe(
      'ws://synthetic.test/api/v1/ws-auth/ws/queue/optional-auth?department=specialist_7&date=2026-11-12'
    );
    // No JWT in the URL (it would leak into logs/history).
    expect(ws.url).not.toContain('synthetic-jwt');
    expect(ws.subprotocols).toEqual(['bearer.synthetic-jwt']);
  });

  it('delivers the RAW MessageEvent to onMessage (wrapper event.data stays parseable)', () => {
    const onMessage = vi.fn();
    const ws = createQueueWebSocket('specialist_7', '2026-11-12', {
      onMessage,
    }) as unknown as FakeWebSocket;

    const frame = JSON.stringify({ type: 'queue_update', data: { action: 'entry_added' } });
    ws.onmessage?.(new FakeMessageEvent(frame) as unknown as MessageEvent);

    expect(onMessage).toHaveBeenCalledTimes(1);
    const delivered = onMessage.mock.calls[0][0] as { data: string };
    // The wrapper contract: event.data is the raw wire payload.
    expect(delivered.data).toBe(frame);
    expect(JSON.parse(delivered.data)).toMatchObject({ type: 'queue_update' });
  });

  it('answers server ping frames with pong automatically (heartbeat stays alive)', () => {
    const onMessage = vi.fn();
    const ws = createQueueWebSocket('specialist_7', '2026-11-12', {
      onMessage,
    }) as unknown as FakeWebSocket;

    ws.onmessage?.(
      new FakeMessageEvent(JSON.stringify({ type: 'ping', timestamp: 't1' })) as unknown as MessageEvent
    );

    expect(ws.sent).toHaveLength(1);
    expect(JSON.parse(ws.sent[0])).toMatchObject({ type: 'pong', timestamp: 't1' });
    // The ping is still observable through the raw-event contract.
    expect(JSON.parse((onMessage.mock.calls[0][0] as { data: string }).data)).toMatchObject({
      type: 'ping',
    });
  });

  it('routes auth-error frames to onAuthError while onMessage keeps the raw event', () => {
    const onMessage = vi.fn();
    const onAuthError = vi.fn();
    const ws = createQueueWebSocket('specialist_7', '2026-11-12', {
      onMessage,
      onAuthError,
    }) as unknown as FakeWebSocket;

    const frame = JSON.stringify({ type: 'error', message: 'Ошибка: аутентификация не пройдена' });
    ws.onmessage?.(new FakeMessageEvent(frame) as unknown as MessageEvent);

    expect(onAuthError).toHaveBeenCalledWith('Ошибка: аутентификация не пройдена');
    expect(JSON.parse((onMessage.mock.calls[0][0] as { data: string }).data)).toMatchObject({
      type: 'error',
    });
  });
});
