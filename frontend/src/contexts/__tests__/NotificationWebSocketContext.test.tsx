import { act, render } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { NotificationWebSocketProvider } from '../NotificationWebSocketContext';

const {
  notificationCenterMock,
  tokenManagerMock,
  loggerMock,
  runtimeMock,
  notifyMock,
  cacheMock,
} = vi.hoisted(() => {
  const notificationCenterMock = {
    appendNotification: vi.fn((notification: unknown) => notification),
    replaceNotifications: vi.fn(),
    updateUnreadSnapshot: vi.fn(),
  };

  const tokenManagerMock = {
    getAccessToken: vi.fn(() => 'token-1'),
    isTokenValid: vi.fn(() => true),
  };

  const loggerMock = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  };

  const runtimeMock = {
    buildWsUrl: vi.fn((path: string) => `ws://localhost:18000${path}`),
  };

  const notifyMock = {
    info: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
  };

  const cacheMock = {
    clearNotificationQueryCache: vi.fn(),
  };

  return {
    notificationCenterMock,
    tokenManagerMock,
    loggerMock,
    runtimeMock,
    notifyMock,
    cacheMock,
  };
});

vi.mock('../NotificationCenterContext', () => ({
  useNotificationCenter: () => notificationCenterMock,
}));

vi.mock('../../utils/tokenManager', () => ({
  tokenManager: tokenManagerMock,
}));

vi.mock('../../utils/logger', () => ({
  default: loggerMock,
}));

vi.mock('../../api/runtime', () => ({
  buildWsUrl: runtimeMock.buildWsUrl,
}));

vi.mock('../../services/notify', () => ({
  default: notifyMock,
}));

vi.mock('../../api/services', () => ({
  clearNotificationQueryCache: cacheMock.clearNotificationQueryCache,
}));

// Cast the notification center mock through unknown so we can read
// mock.calls without fighting the original signature.
const notificationCenterMockTyped = notificationCenterMock as unknown as {
  appendNotification: ReturnType<typeof vi.fn>;
  replaceNotifications: ReturnType<typeof vi.fn>;
  updateUnreadSnapshot: ReturnType<typeof vi.fn>;
};
const tokenManagerMockTyped = tokenManagerMock as unknown as {
  getAccessToken: ReturnType<typeof vi.fn>;
  isTokenValid: ReturnType<typeof vi.fn>;
};

interface MockWsEvent {
  code?: number;
  reason?: string;
  data?: string;
}

interface MockWebSocketInstance {
  url: string;
  readyState: number;
  onopen: ((e?: MockWsEvent) => void) | null;
  onmessage: ((e: MockWsEvent) => void) | null;
  onclose: ((e: MockWsEvent) => void) | null;
  onerror: ((e?: unknown) => void) | null;
  close: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  triggerOpen: () => void;
  triggerMessage: (payload: unknown) => void;
}

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: MockWebSocketInstance[] = [];

  url: string;
  readyState: number;
  onopen: ((e?: MockWsEvent) => void) | null;
  onmessage: ((e: MockWsEvent) => void) | null;
  onclose: ((e: MockWsEvent) => void) | null;
  onerror: ((e?: unknown) => void) | null;
  close: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;

  constructor(url: string) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;
    this.send = vi.fn();
    this.close = vi.fn(() => {
      this.readyState = MockWebSocket.CLOSED;
      this.onclose?.({ code: 1000, reason: 'Unmount' });
    });
    MockWebSocket.instances.push(this as unknown as MockWebSocketInstance);
  }

  triggerOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  triggerMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

function Harness() {
  return <div data-testid="ws-harness" />;
}


function renderProvider(pathname: string) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <NotificationWebSocketProvider>
        <Harness />
      </NotificationWebSocketProvider>
    </MemoryRouter>,
  );
}

describe('NotificationWebSocketContext', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.clearAllMocks();
    vi.useFakeTimers();
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    Object.defineProperty(window, 'WebSocket', {
      writable: true,
      value: MockWebSocket,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('defers socket creation until after the mount cycle on protected routes', async () => {
    renderProvider('/doctor/cardiology');

    expect(MockWebSocket.instances).toHaveLength(0);

    await act(async () => {
      vi.runAllTimers();
    });

    expect(MockWebSocket.instances).toHaveLength(1);
    // P1-6: token now sent via subprotocol, not URL query param
    expect(MockWebSocket.instances[0].url).toBe(
      'ws://localhost:18000/api/v1/ws/notifications/connect',
    );
  });

  it('does not connect on public routes even after pending timers flush', async () => {
    renderProvider('/login');

    await act(async () => {
      vi.runAllTimers();
    });

    expect(MockWebSocket.instances).toHaveLength(0);
    expect(tokenManagerMockTyped.isTokenValid).not.toHaveBeenCalled();
  });

  it('normalizes legacy queue_changed websocket events to queue_update', async () => {
    renderProvider('/doctor/cardiology');

    await act(async () => {
      vi.runAllTimers();
    });

    const socket = MockWebSocket.instances[0];
    await act(async () => {
      // Fixture contract: parseWsEvent (zod WsMessageSchema) requires a top-level
      // `type: string`. The event_type alias lives in the nested `notification`
      // payload and is resolved to 'queue_update' by normalizePayload() via
      // TYPE_ALIASES. This matches the production WS event contract.
      socket.triggerMessage({
        type: 'notification',
        notification: {
          event_type: 'queue_changed',
          message: 'Пациент вызван',
        },
      });
    });

    expect(notificationCenterMockTyped.appendNotification).toHaveBeenCalledTimes(1);
    const [notification, source] = notificationCenterMockTyped.appendNotification.mock.calls[0] as [
      { type: string; title: string },
      string
    ];
    expect(notification.type).toBe('queue_update');
    expect(notification.title).toBe('Обновление очереди');
    expect(source).toBe('ws');
  });

  it('normalizes diagnostics_return websocket events to diagnostics_return_needed', async () => {
    renderProvider('/doctor/cardiology');

    await act(async () => {
      vi.runAllTimers();
    });

    const socket = MockWebSocket.instances[0];
    await act(async () => {
      // Fixture contract: parseWsEvent (zod WsMessageSchema) requires a top-level
      // `type: string`. The event_type alias lives in the nested `notification`
      // payload and is resolved to 'diagnostics_return_needed' by normalizePayload()
      // via TYPE_ALIASES. This matches the production WS event contract.
      socket.triggerMessage({
        type: 'notification',
        notification: {
          event_type: 'diagnostics_return',
          title: 'Повторная диагностика',
          message: 'Нужно вернуться на диагностику',
        },
      });
    });

    expect(notificationCenterMockTyped.appendNotification).toHaveBeenCalledTimes(1);
    const [notification, source] = notificationCenterMockTyped.appendNotification.mock.calls[0] as [
      { type: string; title: string },
      string
    ];
    expect(notification.type).toBe('diagnostics_return_needed');
    expect(notification.title).toBe('Повторная диагностика');
    expect(source).toBe('ws');
  });

  it.each([
    ['lab_results', 'Результат анализа', 'info'],
    ['new_appointment', 'Новая запись', 'info'],
    ['message_received', 'Новое сообщение', 'info'],
    ['security_alert', 'Системная безопасность', 'warning'],
  ] as const)(
    'accepts canonical notification transport carrying %s event without an event-type allowlist',
    async (eventType, title, toastLevel) => {
      renderProvider('/doctor/cardiology');

      await act(async () => {
        vi.runAllTimers();
      });

      const socket = MockWebSocket.instances[0];
      const deliveryId = `synthetic-${eventType}-1`;

      await act(async () => {
        socket.triggerMessage({
          type: 'notification',
          event_type: eventType,
          delivery_id: deliveryId,
          notification: {
            delivery_id: deliveryId,
            event_type: eventType,
            title,
            message: 'Синтетическое уведомление',
            role: 'doctor',
          },
        });
      });

      expect(notificationCenterMockTyped.appendNotification).toHaveBeenCalledTimes(1);
      const [notification, source] =
        notificationCenterMockTyped.appendNotification.mock.calls[0] as [
          { type: string; title: string; message: string; delivery_id: string },
          string,
        ];
      expect(source).toBe('ws');
      expect(notification).toMatchObject({
        type: eventType,
        title,
        message: 'Синтетическое уведомление',
        delivery_id: deliveryId,
      });
      expect(cacheMock.clearNotificationQueryCache).toHaveBeenCalledTimes(1);
      expect(notifyMock[toastLevel]).toHaveBeenCalledWith(
        `${title}: Синтетическое уведомление`,
      );
    },
  );

  it.each([
    { type: 'connection_established', unread_count: 2 },
    { type: 'notification_read_ack', delivery_id: 'synthetic-1', unread_count: 1 },
    { type: 'notification_sync_response', items: [], unread_count: 0 },
    { type: 'ping' },
    { type: 'unknown', notification: { event_type: 'lab_results', title: 'Not a canonical transport' } },
  ])('does not append a delivery for a non-notification transport %#', async (payload) => {
    renderProvider('/doctor/cardiology');

    await act(async () => {
      vi.runAllTimers();
    });

    await act(async () => {
      MockWebSocket.instances[0].triggerMessage(payload);
    });

    expect(notificationCenterMockTyped.appendNotification).not.toHaveBeenCalled();
    expect(notifyMock.info).not.toHaveBeenCalled();
    expect(notifyMock.warning).not.toHaveBeenCalled();
  });

  it('requests bounded inbox replay only after handshake, once per connection', async () => {
    renderProvider('/doctor/cardiology');
    await act(async () => {
      vi.runAllTimers();
    });

    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.triggerOpen();
    });
    expect(socket.send).not.toHaveBeenCalled();

    await act(async () => {
      socket.triggerMessage({
        type: 'connection_established',
        user_id: 41,
        unread_count: 3,
      });
      socket.triggerMessage({
        type: 'connection_established',
        user_id: 41,
        unread_count: 3,
      });
    });

    expect(socket.send).toHaveBeenCalledTimes(1);
    expect(JSON.parse(socket.send.mock.calls[0][0] as string)).toEqual({
      type: 'notification_sync',
      limit: 50,
    });
    expect(notificationCenterMockTyped.updateUnreadSnapshot).toHaveBeenCalled();
    expect(notifyMock.info).not.toHaveBeenCalled();
    expect(notificationCenterMockTyped.appendNotification).not.toHaveBeenCalled();
  });

  it('reconciles replayed persisted delivery without a second toast', async () => {
    renderProvider('/doctor/cardiology');
    await act(async () => {
      vi.runAllTimers();
    });

    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.triggerOpen();
      socket.triggerMessage({ type: 'connection_established', unread_count: 2 });
      socket.triggerMessage({
        type: 'notification_sync_response',
        unread_count: 2,
        items: [{
          delivery_id: 'synthetic-offline-1',
          sequence_id: 77,
          event_type: 'lab_results',
          title: 'Synthetic result',
          message: 'Persisted offline',
        }],
      });
    });

    expect(socket.send).toHaveBeenCalledTimes(1);
    expect(notificationCenterMockTyped.replaceNotifications).toHaveBeenCalledTimes(1);
    const [items, meta] =
      notificationCenterMockTyped.replaceNotifications.mock.calls[0] as [
        Array<{ delivery_id: string; event_type: string }>,
        { source: string; unreadSnapshot: { total: number }; lastSyncAt: string },
      ];
    expect(items).toEqual([expect.objectContaining({
      delivery_id: 'synthetic-offline-1',
      event_type: 'lab_results',
    })]);
    expect(meta.source).toBe('ws');
    expect(meta.unreadSnapshot.total).toBe(2);
    expect(meta.lastSyncAt).toEqual(expect.any(String));
    expect(notificationCenterMockTyped.appendNotification).not.toHaveBeenCalled();
    expect(notifyMock.info).not.toHaveBeenCalled();
    expect(notifyMock.warning).not.toHaveBeenCalled();
  });

  it('replays again on a fresh reconnect but never responds to stale socket messages', async () => {
    renderProvider('/doctor/cardiology');
    await act(async () => {
      vi.runAllTimers();
    });
    const first = MockWebSocket.instances[0];

    await act(async () => {
      first.triggerOpen();
      first.triggerMessage({ type: 'connection_established', unread_count: 1 });
    });
    expect(first.send).toHaveBeenCalledTimes(1);

    await act(async () => {
      first.close();
      vi.advanceTimersByTime(3000);
    });
    expect(MockWebSocket.instances).toHaveLength(2);
    const second = MockWebSocket.instances[1];

    await act(async () => {
      second.triggerOpen();
      first.triggerMessage({ type: 'connection_established', unread_count: 7 });
      second.triggerMessage({ type: 'connection_established', unread_count: 2 });
    });
    expect(first.send).toHaveBeenCalledTimes(1);
    expect(second.send).toHaveBeenCalledTimes(1);
    expect(JSON.parse(second.send.mock.calls[0][0] as string)).toEqual({
      type: 'notification_sync',
      limit: 50,
    });
  });


});
