import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// DISPLAYWS-FE-004 (audit PR #3961): the public TV board must keep
// reconnecting with BOUNDED exponential backoff + jitter after abnormal
// closes — the previous hard cap of 5 attempts left a kiosk disconnected
// until a full remount/reload. Manual close (code 1000 / close()) still
// stops the retry loop.

const wsMock = vi.hoisted(() => ({
  openDisplayBoardWS: vi.fn(),
}));
vi.mock('../../utils/logger', () => ({
  default: { log: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../utils/tokenManager', () => ({
  tokenManager: { getAccessToken: vi.fn(() => undefined) },
}));
vi.mock('../../api/runtime', () => ({
  buildWsUrl: (path: string) => `ws://synthetic${path}`,
}));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;
  readyState = FakeWebSocket.CONNECTING;
  onopen: ((ev?: unknown) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  onerror: ((ev?: unknown) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  sent: string[] = [];
  closedCodes: Array<[number, string]> = [];

  constructor(public url: string, public protocols?: string[]) {
    FakeWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close(code = 1000, reason = '') {
    this.closedCodes.push([code, reason]);
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code });
  }
  // synthetic server-side lifecycle
  simulateOpen() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }
  simulateAbnormalClose(code = 1006) {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code });
  }
}

vi.stubGlobal('WebSocket', FakeWebSocket);

import { openDisplayBoardWS } from '../../api/ws';

describe('openDisplayBoardWS reconnect policy (DISPLAYWS-FE-004)', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_ENABLE_WS', '1');
    vi.useFakeTimers();
    vi.clearAllMocks();
    FakeWebSocket.instances = [];
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('keeps reconnecting past five abnormal closes with capped backoff', () => {
    openDisplayBoardWS('main_board', () => {}, () => {}, () => {});
    expect(FakeWebSocket.instances.length).toBe(1);

    // One successful session, then a PROLONGED outage: every reconnect
    // socket fails before opening (abnormal close) — the old cap stopped
    // after five attempts and the kiosk stayed dead until a remount.
    FakeWebSocket.instances[0].simulateOpen();
    FakeWebSocket.instances[0].simulateAbnormalClose(1006);
    for (let round = 0; round < 6; round++) {
      vi.advanceTimersByTime(30500);
      const socket = FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
      socket.simulateAbnormalClose(1006);
    }

    // 1 initial + 6 reconnect attempts — attempts must never be exhausted.
    expect(FakeWebSocket.instances.length).toBe(7);
  });

  it('schedules reconnect attempts at bounded increasing delays', () => {
    openDisplayBoardWS('main_board', () => {}, () => {}, () => {});
    FakeWebSocket.instances[0].simulateOpen();
    FakeWebSocket.instances[0].simulateAbnormalClose(1006);

    // Attempt 1: 3000ms base (+ jitter < 500ms) — not before 3000ms
    // (no tight loop), and by 3500ms.
    vi.advanceTimersByTime(2999);
    expect(FakeWebSocket.instances.length).toBe(1);
    vi.advanceTimersByTime(501);
    expect(FakeWebSocket.instances.length).toBe(2);
    FakeWebSocket.instances[1].simulateAbnormalClose(1006);

    // Attempt 2: 6000ms base — must NOT fire before 6000ms (jitter only
    // adds), and must fire within 6500ms.
    vi.advanceTimersByTime(5999);
    expect(FakeWebSocket.instances.length).toBe(2);
    vi.advanceTimersByTime(501);
    expect(FakeWebSocket.instances.length).toBe(3);
    FakeWebSocket.instances[2].simulateAbnormalClose(1006);

    // Attempt 3: 12000ms base — the backoff keeps growing (12s), never a
    // tight loop. Generous window: the exact fire instant depends on the
    // jitter accumulated at the previous attempts.
    vi.advanceTimersByTime(11000);
    expect(FakeWebSocket.instances.length).toBe(3);
    vi.advanceTimersByTime(3000);
    expect(FakeWebSocket.instances.length).toBe(4);
  });

  it('requests a fresh board-scoped token before every connection', async () => {
    const tokenProvider = vi.fn()
      .mockResolvedValueOnce('device-token-one')
      .mockResolvedValueOnce('device-token-two');
    openDisplayBoardWS('main_board', () => {}, () => {}, () => {}, tokenProvider);
    await Promise.resolve();

    expect(FakeWebSocket.instances[0].protocols).toEqual(['bearer.device-token-one']);
    FakeWebSocket.instances[0].simulateOpen();
    FakeWebSocket.instances[0].simulateAbnormalClose(1008);
    vi.advanceTimersByTime(3500);
    await Promise.resolve();

    expect(tokenProvider).toHaveBeenCalledTimes(2);
    expect(FakeWebSocket.instances[1].protocols).toEqual(['bearer.device-token-two']);
  });

  it('waits for provisioning after a missing or revoked device session', async () => {
    const provisioningError = Object.assign(new Error('Provisioning required'), {
      code: 'DISPLAY_DEVICE_PROVISIONING_REQUIRED',
    });
    const tokenProvider = vi.fn().mockRejectedValue(provisioningError);

    openDisplayBoardWS('main_board', () => {}, () => {}, () => {}, tokenProvider);
    await Promise.resolve();
    await Promise.resolve();

    expect(tokenProvider).toHaveBeenCalledTimes(1);
    expect(FakeWebSocket.instances).toHaveLength(0);
    vi.advanceTimersByTime(120_000);
    await Promise.resolve();
    expect(tokenProvider).toHaveBeenCalledTimes(1);
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it('checks device provisioning when WebSockets are disabled', async () => {
    vi.stubEnv('VITE_ENABLE_WS', '0');
    const tokenProvider = vi.fn().mockResolvedValue('device-token');
    const onConnect = vi.fn();

    openDisplayBoardWS('main_board', () => {}, onConnect, () => {}, tokenProvider);
    await Promise.resolve();
    await Promise.resolve();

    expect(tokenProvider).toHaveBeenCalledTimes(1);
    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(onConnect).not.toHaveBeenCalled();
  });

  it('does not reconnect after a manual close (code 1000)', () => {
    const close = openDisplayBoardWS('main_board', () => {}, () => {}, () => {});
    const socket = FakeWebSocket.instances[0];
    socket.simulateOpen();
    close();
    // Manual close(): handlers were nulled; a synthetic 1000 close arrives.
    socket.onclose?.({ code: 1000 });
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances.length).toBe(1);
  });
});
