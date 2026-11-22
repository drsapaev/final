/**
 * WSQ-FE-001/002 (audit 3886, ledger group 5 — WebSocket reconnect):
 *
 * WSQ-FE-001 (P2): the reconnect budget (reconnectAttemptRef) lives for the
 *   hook's whole lifetime — a previous subscription that exhausted its five
 *   attempts leaves a NEW doctor/date subscription with no retries.
 * WSQ-FE-002 (P2): every close with code 1000 is treated as a deliberate
 *   client close — a SERVER-initiated normal close permanently disables
 *   live refresh (polling-only) until remount.
 *
 * Red-first: on pre-fix source both tests fail for the documented reasons.
 */
import React from 'react';
import { act, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../utils/logger', () => ({
  default: { log: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../utils/tokenManager', () => ({
  tokenManager: { getAccessToken: () => 'ws-test-token' },
}));
vi.mock('../../api/runtime', () => ({
  buildWsUrl: (path: string) => `wss://queue.test${path}`,
}));

import { useQueueWebSocket } from '../useQueueWebSocket';

type MockSocket = {
  url: string;
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onerror: ((error: unknown) => void) | null;
  onclose: ((event: { code: number; reason?: string }) => void) | null;
  close: () => void;
};

const sockets: MockSocket[] = [];
let socketIndex = 0;

class FakeWebSocket {
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((error: unknown) => void) | null = null;
  onclose: ((event: { code: number; reason?: string }) => void) | null = null;
  constructor(url: string) {
    this.url = url;
    sockets.push(this);
  }
  close() {
    /* recorded by the test via sockets[] */
  }
  static get OPEN() {
    return 1;
  }
}

function Harness(props: { specialistId?: string; date?: string; enabled?: boolean; onUpdate?: () => void }) {
  const { connectionState } = useQueueWebSocket(props);
  return <div data-testid="ws-state">{connectionState}</div>;
}

/** Fails the latest socket exactly once with the given close code. */
function failLatestSocket(code = 1006) {
  const ws = sockets[sockets.length - 1];
  if (ws && ws.onclose) {
    ws.onclose({ code, reason: 'synthetic failure' });
  }
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  sockets.length = 0;
  socketIndex = 0;
  global.WebSocket = FakeWebSocket as never;
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe('WSQ-FE-001: the reconnect budget is per subscription identity', () => {
  it('a new doctor subscription gets a FRESH retry budget after the old one exhausted it', async () => {
    const { rerender } = render(<Harness specialistId="doctor-a" date="2026-11-06" />);

    // Exhaust doctor A's budget: five failed connections with their retries.
    await act(async () => {
      failLatestSocket(1006);
    });
    for (let attempt = 1; attempt <= 4; attempt += 1) {
      await act(async () => {
        vi.advanceTimersByTime(31000);
      });
      await act(async () => {
        failLatestSocket(1006);
      });
    }
    // A's budget is used up: 5 sockets created so far.
    expect(sockets.length).toBe(5);

    // Switch to doctor B in the SAME mounted hook — new subscription.
    rerender(<Harness specialistId="doctor-b" date="2026-11-06" />);

    // The new subscription opened its own socket…
    expect(sockets.length).toBe(6);
    expect(sockets[5].url).toContain('specialist_doctor-b');

    // …and its FIRST failure must still get a bounded retry with a fresh
    // budget (pre-fix: the old counter 5 blocked every retry for B).
    await act(async () => {
      failLatestSocket(1006);
    });
    await act(async () => {
      vi.advanceTimersByTime(31000);
    });
    expect(sockets.length).toBe(7);
    expect(sockets[6].url).toContain('specialist_doctor-b');
  });
});

describe('WSQ-FE-002: a server-initiated normal close still reconnects', () => {
  it('remote close with code 1000 schedules a bounded reconnect', async () => {
    render(<Harness specialistId="doctor-a" date="2026-11-06" />);

    // The SERVER closes the socket normally (code 1000) — not a client
    // cleanup. Live refresh must reconnect within the bounded budget.
    await act(async () => {
      const ws = sockets[sockets.length - 1];
      ws.onclose?.({ code: 1000, reason: 'server lifecycle close' });
    });

    // A reconnect attempt is scheduled (pre-fix: code 1000 returned early
    // and the hook went polling-only forever).
    await act(async () => {
      vi.advanceTimersByTime(31000);
    });
    expect(sockets.length).toBe(2);
  });

  it('an unmount causes ZERO reconnects', async () => {
    const { unmount } = render(<Harness specialistId="doctor-a" date="2026-11-06" />);
    unmount();

    await act(async () => {
      vi.advanceTimersByTime(120000);
    });
    expect(sockets.length).toBe(1);
  });
});
