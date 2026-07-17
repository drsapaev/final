import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect } from 'react';
import PropTypes from 'prop-types';
import { MemoryRouter } from 'react-router-dom';
import { ChatProvider, useChat } from '../ChatContext.tsx';
import { MESSAGE_EVENT_TYPES } from '../../constants/messagingContract.ts';

const {
  authMock,
  messagesApiMock,
  pushNotificationsMock,
  loggerMock,
  tokenManagerMock,
  runtimeMock,
} = vi.hoisted(() => {
  const authMock = {
    getState: vi.fn(() => ({
      profile: { id: 1, username: 'alice', full_name: 'Alice Demo' },
      token: 'token-1',
    })),
    subscribe: vi.fn(() => () => {}),
  };

  const messagesApiMock = {
    getConversations: vi.fn().mockResolvedValue({ conversations: [], total_unread: 0 }),
    getConversation: vi.fn().mockResolvedValue({ messages: [], has_more: false, total: 0 }),
    markAsRead: vi.fn().mockResolvedValue({ id: 99, is_read: true }),
    getUnreadCount: vi.fn().mockResolvedValue(0),
    sendMessage: vi.fn(),
    deleteMessage: vi.fn(),
    getAvailableUsers: vi.fn().mockResolvedValue([]),
    toggleReaction: vi.fn(),
    uploadFile: vi.fn(),
  };

  const pushNotificationsMock = {
    showMessageNotification: vi.fn(),
  };

  const loggerMock = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  };

  const tokenManagerMock = {
    getAccessToken: vi.fn(() => 'token-1'),
    isTokenValid: vi.fn(() => true),
  };

  const runtimeMock = {
    getWsBaseUrl: vi.fn(() => 'ws://localhost:18000'),
  };

  return {
    authMock,
    messagesApiMock,
    pushNotificationsMock,
    loggerMock,
    tokenManagerMock,
    runtimeMock,
  };
});

vi.mock('../../stores/auth', () => ({
  default: authMock,
}));

vi.mock('../../api/messages', () => messagesApiMock);

vi.mock('../../services/pushNotifications', () => ({
  pushNotifications: pushNotificationsMock,
}));

vi.mock('../../utils/logger', () => ({
  default: loggerMock,
}));

vi.mock('../../utils/tokenManager', () => ({
  default: tokenManagerMock,
}));

vi.mock('../../api/runtime', () => ({
  getWsBaseUrl: runtimeMock.getWsBaseUrl,
}));

class MockAudioContext {
  constructor() {
    this.currentTime = 0;
    this.destination = {};
  }

  createOscillator() {
    return {
      connect: vi.fn(),
      frequency: { value: 0 },
      type: 'sine',
      start: vi.fn(),
      stop: vi.fn(),
    };
  }

  createGain() {
    return {
      connect: vi.fn(),
      gain: {
        setValueAtTime: vi.fn(),
        exponentialRampToValueAtTime: vi.fn(),
      },
    };
  }
}

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.sent = [];
    MockWebSocket.instances.push(this);
  }

  send = vi.fn((payload) => {
    this.sent.push(payload);
  });

  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code: 1000 });
  });

  triggerOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  triggerMessage(data) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

MockWebSocket.instances = [];

function ChatHarness({ openChat = true }) {
  const {
    messages,
    unreadCount,
    activeConversation,
    isChatOpen,
    setActiveConversation,
    setIsChatOpen,
  } = useChat();

  useEffect(() => {
    setActiveConversation(2);
    setIsChatOpen(openChat);
  }, [openChat, setActiveConversation, setIsChatOpen]);

  const latestMessage = messages[0];

  return (
    <div>
      <div data-testid="active-conversation">{String(activeConversation ?? '')}</div>
      <div data-testid="chat-open">{String(isChatOpen)}</div>
      <div data-testid="unread-count">{String(unreadCount)}</div>
      <div data-testid="message-count">{String(messages.length)}</div>
      <div data-testid="latest-message-read">{String(latestMessage?.is_read ?? false)}</div>
    </div>
  );
}

ChatHarness.propTypes = {
  openChat: PropTypes.bool,
};

function renderChat(openChat = true) {
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <ChatProvider>
        <ChatHarness openChat={openChat} />
      </ChatProvider>
    </MemoryRouter>,
  );
}

describe('ChatContext', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.clearAllMocks();
    global.WebSocket = MockWebSocket;
    Object.defineProperty(window, 'WebSocket', {
      writable: true,
      value: MockWebSocket,
    });
    Object.defineProperty(window, 'AudioContext', {
      writable: true,
      value: MockAudioContext,
    });
    Object.defineProperty(window, 'webkitAudioContext', {
      writable: true,
      value: MockAudioContext,
    });
    Object.defineProperty(document, 'hasFocus', {
      writable: true,
      value: vi.fn(() => true),
    });
  });

  it('hydrates the inbox immediately after auth is available, before websocket open', async () => {
    renderChat(true);

    await waitFor(() => {
      expect(messagesApiMock.getConversations).toHaveBeenCalled();
      expect(messagesApiMock.getUnreadCount).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.triggerOpen();
    });

    await waitFor(() => {
      expect(messagesApiMock.getConversations).toHaveBeenCalledTimes(1);
      expect(messagesApiMock.getUnreadCount).toHaveBeenCalledTimes(1);
    });
  });

  it('does not load chat data on public routes', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <ChatProvider>
          <ChatHarness openChat />
        </ChatProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('message-count')).toHaveTextContent('0');
      expect(screen.getByTestId('unread-count')).toHaveTextContent('0');
    });

    expect(messagesApiMock.getConversations).not.toHaveBeenCalled();
    expect(messagesApiMock.getUnreadCount).not.toHaveBeenCalled();
  });

  it('auto-marks incoming messages as read when the active conversation is open and focused', async () => {
    renderChat(true);

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });
    await waitFor(() => {
      expect(screen.getByTestId('active-conversation')).toHaveTextContent('2');
      expect(screen.getByTestId('chat-open')).toHaveTextContent('true');
    });

    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.triggerOpen();
    });

    await act(async () => {
      socket.triggerMessage({
        type: MESSAGE_EVENT_TYPES.NEW_MESSAGE,
        contract_version: '2026-03',
        message: {
          id: 99,
          sender_id: 2,
          recipient_id: 1,
          content: 'Привет из чата',
          is_read: false,
          created_at: '2026-03-29T10:00:00Z',
        },
      });
    });

    await waitFor(() => {
      expect(messagesApiMock.markAsRead).toHaveBeenCalledWith(99);
      expect(screen.getByTestId('message-count')).toHaveTextContent('1');
      expect(screen.getByTestId('latest-message-read')).toHaveTextContent('true');
      expect(screen.getByTestId('unread-count')).toHaveTextContent('0');
    });
  });

  it('logs a contract version mismatch once without breaking message handling', async () => {
    renderChat(true);

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.triggerOpen();
    });

    await act(async () => {
      socket.triggerMessage({
        type: MESSAGE_EVENT_TYPES.NEW_MESSAGE,
        contract_version: '2026-04',
        message: {
          id: 101,
          sender_id: 2,
          recipient_id: 1,
          content: 'Сообщение из будущей версии',
          is_read: false,
          created_at: '2026-03-29T10:02:00Z',
        },
      });
    });

    await waitFor(() => {
      expect(loggerMock.warn).toHaveBeenCalledWith(
        '[FIX:WS] Messaging contract version mismatch',
        expect.objectContaining({
          expected: '2026-03',
          received: '2026-04',
          type: 'new_message',
        }),
      );
      expect(screen.getByTestId('message-count')).toHaveTextContent('1');
    });
  });

  it('does not auto-mark incoming messages when the chat is closed', async () => {
    messagesApiMock.getConversations.mockResolvedValueOnce({
      conversations: [],
      total_unread: 1,
    });

    renderChat(false);

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });
    await waitFor(() => {
      expect(screen.getByTestId('active-conversation')).toHaveTextContent('2');
      expect(screen.getByTestId('chat-open')).toHaveTextContent('false');
    });

    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.triggerOpen();
    });

    await act(async () => {
      socket.triggerMessage({
        type: MESSAGE_EVENT_TYPES.NEW_MESSAGE,
        contract_version: '2026-03',
        message: {
          id: 100,
          sender_id: 2,
          recipient_id: 1,
          content: 'Непрочитанное сообщение',
          is_read: false,
          created_at: '2026-03-29T10:05:00Z',
        },
      });
    });

    await waitFor(() => {
      expect(messagesApiMock.markAsRead).not.toHaveBeenCalled();
      expect(screen.getByTestId('message-count')).toHaveTextContent('1');
      expect(screen.getByTestId('latest-message-read')).toHaveTextContent('false');
      expect(screen.getByTestId('unread-count')).toHaveTextContent('1');
    });
  });
});
