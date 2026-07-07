import { act, render } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import PropTypes from 'prop-types';
import { MemoryRouter } from 'react-router-dom';
import { NotificationWebSocketProvider } from '../NotificationWebSocketContext.jsx';

const {
  notificationCenterMock,
  tokenManagerMock,
  loggerMock,
  runtimeMock,
  notifyMock,
  cacheMock,
} = vi.hoisted(() => {
  const notificationCenterMock = {
    appendNotification: vi.fn((notification) => notification),
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
    buildWsUrl: vi.fn((path) => `ws://localhost:18000${path}`),
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

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    MockWebSocket.instances.push(this);
  }

  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code: 1000, reason: 'Unmount' });
  });

  triggerOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  triggerMessage(payload) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

MockWebSocket.instances = [];

function Harness() {
  return <div data-testid="ws-harness" />;
}

Harness.propTypes = {};

function renderProvider(pathname) {
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
    global.WebSocket = MockWebSocket;
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
    expect(tokenManagerMock.isTokenValid).not.toHaveBeenCalled();
  });

  it('normalizes legacy queue_changed websocket events to queue_update', async () => {
    renderProvider('/doctor/cardiology');

    await act(async () => {
      vi.runAllTimers();
    });

    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.triggerMessage({
        notification: {
          event_type: 'queue_changed',
          message: 'Пациент вызван',
        },
      });
    });

    expect(notificationCenterMock.appendNotification).toHaveBeenCalledTimes(1);
    const [notification, source] = notificationCenterMock.appendNotification.mock.calls[0];
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
      socket.triggerMessage({
        notification: {
          event_type: 'diagnostics_return',
          title: 'Повторная диагностика',
          message: 'Нужно вернуться на диагностику',
        },
      });
    });

    expect(notificationCenterMock.appendNotification).toHaveBeenCalledTimes(1);
    const [notification, source] = notificationCenterMock.appendNotification.mock.calls[0];
    expect(notification.type).toBe('diagnostics_return_needed');
    expect(notification.title).toBe('Повторная диагностика');
    expect(source).toBe('ws');
  });
});
