import { createContext, useContext, useEffect, useState, useRef, useCallback, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import PropTypes from 'prop-types';
import { getWsBaseUrl } from '../api/runtime';
import auth from '../stores/auth';
import * as messagesApi from '../api/messages';
import { pushNotifications } from '../services/pushNotifications';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import {
  MESSAGE_EVENT_TYPES,
  MESSAGING_CONTRACT_VERSION,
  isSupportedMessagingContractVersion,
} from '../constants/messagingContract';
import { isPublicRoutePath } from '../routing/routeSelectors';

// Domain value objects. The backend chat protocol is dynamic, so we model
// the canonical surface here and let extra fields ride along via the
// index signature. These intentionally match the shape produced by
// api/messages.ts (which is still implicit-any — typed in a later batch).
interface ChatReaction {
  emoji: string;
  count: number;
  user_ids?: number[];
}

interface ChatMessage {
  id: number;
  sender_id: number;
  recipient_id: number;
  sender_name?: string;
  content?: string;
  is_read?: boolean;
  reactions?: ChatReaction[];
  created_at?: string;
  [key: string]: unknown;
}

interface Conversation {
  user_id: number;
  unread_count?: number;
  last_message?: string;
  last_message_at?: string;
  [key: string]: unknown;
}

interface AvailableUser {
  id: number;
  name?: string;
  [key: string]: unknown;
}

interface ConversationsResponse {
  conversations?: Conversation[];
  total_unread?: number;
}

interface ConversationResponse {
  messages?: ChatMessage[];
  has_more?: boolean;
}

interface UnreadCountResponse {
  count?: number;
}

interface AvailableUsersResponse {
  users?: AvailableUser[];
}

interface AuthState {
  token?: string | null;
  profile?: { id?: number | null; [key: string]: unknown } | null;
  [key: string]: unknown;
}

interface WsIncomingMessage {
  type?: string;
  contract_version?: string;
  message?: ChatMessage;
  sender_id?: number | string;
  is_typing?: boolean;
  message_id?: number;
  message_ids?: number[];
  users?: Record<string, unknown>;
  reactions?: ChatReaction[];
  [key: string]: unknown;
}

interface ChatContextValue {
  conversations: Conversation[];
  messages: ChatMessage[];
  activeConversation: number | null;
  unreadCount: number;
  isConnected: boolean;
  isLoading: boolean;
  typingUsers: Record<string, unknown>;
  isChatOpen: boolean;
  setIsChatOpen: (open: boolean) => void;
  mutedConversations: Set<number>;
  setMutedConversations: (next: Set<number>) => void;
  onlineUsers: Record<string, unknown>;
  requestOnlineStatus: (userIds: number[]) => void;
  loadConversations: (options?: { syncUnread?: boolean }) => Promise<void>;
  loadMessages: (userId: number) => Promise<void>;
  sendMessage: (recipientId: number, content: string) => Promise<ChatMessage>;
  closeConversation: () => void;
  setActiveConversation: (userId: number | null) => void;
  searchUsers: (query: string) => Promise<AvailableUser[]>;
  sendTyping: (recipientId: number, isTyping: boolean) => void;
  refreshUnreadCount: () => Promise<void>;
  hasMore: boolean;
  loadMoreMessages: () => Promise<void>;
  toggleReaction: (messageId: number, reaction: string) => Promise<void>;
  deleteMessage: (messageId: number) => Promise<void>;
  uploadFile: (recipientId: number, file: File) => Promise<ChatMessage>;
}

interface ChatProviderProps {
  children: ReactNode;
}

const ChatContext = createContext<ChatContextValue | null>(null);

// window.setTimeout returns number under DOM, but vitest/globals injects
// Node typings where setTimeout returns NodeJS.Timeout. Anchor refs to
// number explicitly so we don't depend on which overload resolves.
type TimeoutHandle = number;

export const ChatProvider = ({ children }: ChatProviderProps) => {
  const location = useLocation();
  const [authState, setAuthState] = useState<AuthState>(() => auth.getState() as AuthState);
  const user = authState.profile;
  const token = authState.token;
  const isBoardRoute = location.pathname.startsWith('/queue-board') || location.pathname.startsWith('/display-board');
  const isPublicRoute = isPublicRoutePath(location.pathname);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeConversation, setActiveConversation] = useState<number | null>(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [typingUsers, setTypingUsers] = useState<Record<string, unknown>>({});
  const [isChatOpen, setIsChatOpen] = useState<boolean>(false); // Track if chat window is open
  // PR-71: muted conversations (client-side, no sound/notification for these)
  const [mutedConversations, setMutedConversations] = useState<Set<number>>(new Set());
  const [onlineUsers, setOnlineUsers] = useState<Record<string, unknown>>({}); // Track online status of users

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<TimeoutHandle | null>(null);
  const activeConversationRef = useRef<number | null>(activeConversation);
  const retryCountRef = useRef<number>(0);
  const readSyncInFlightRef = useRef<Set<number>>(new Set());
  const contractVersionMismatchRef = useRef<boolean>(false);
  const initialConversationLoadUserRef = useRef<number | null>(null);
  // PR-68 / P0-2: singleton AudioContext to prevent leak
  const chatAudioContextRef = useRef<AudioContext | null>(null);

  // Храним актуальные функции в ref
  // Это предотвращает разрыв соединения WebSocket при обновлении функций/стейта
  const handleNewMessageRef = useRef<((message: ChatMessage) => void) | null>(null);
  const loadConversationsRef = useRef<((options?: { syncUnread?: boolean }) => Promise<void>) | null>(null);
  const chatSnapshotSyncUserRef = useRef<number | null>(null);

  // Синхронизация ref activeConversation
  useEffect(() => {
    activeConversationRef.current = activeConversation;
  }, [activeConversation]);

  const resetChatState = useCallback(() => {
    setConversations([]);
    setMessages([]);
    setActiveConversation(null);
    setUnreadCount(0);
    setIsConnected(false);
    setIsLoading(false);
    setTypingUsers({});
    setOnlineUsers({});
    setIsChatOpen(false);
  }, []);

  // Подписка на auth
  useEffect(() => {
    const unsubscribe = auth.subscribe((state) => {
      setAuthState(state as AuthState);
    });
    return unsubscribe;
  }, []);

  const markConversationLocallyRead = useCallback((userId: number): void => {
    if (!userId) return;

    setConversations((prev) => {
      let clearedUnread = 0;
      const next = prev.map((conversation) => {
        if (conversation.user_id !== userId) {
          return conversation;
        }

        clearedUnread = Number(conversation.unread_count || 0);
        if (!clearedUnread) {
          return conversation;
        }

        return {
          ...conversation,
          unread_count: 0,
        };
      });

      if (clearedUnread > 0) {
        setUnreadCount((prevUnread) => Math.max(0, prevUnread - clearedUnread));
      }

      return next;
    });
  }, []);

  // Загрузка бесед
  const loadConversations = useCallback(async ({ syncUnread = true } = {}): Promise<void> => {
    if (!user || isBoardRoute || isPublicRoute) return;
    try {
      const data = (await messagesApi.getConversations()) as ConversationsResponse;
      setConversations(data.conversations || []);
      if (syncUnread) {
        setUnreadCount(data.total_unread || 0);
      }
    } catch (error) {
      const err = error as { response?: { status?: number } };
      const status = err?.response?.status;
      if (status === 401 || status === 403) {
        logger.info('[FIX:CHAT] Skipping conversations load due to auth state', {
          status,
          path: location.pathname,
        });
        return;
      }
      logger.error('Failed to load conversations:', error);
    }
  }, [isBoardRoute, isPublicRoute, location.pathname, user]);

  const markMessageAsRead = useCallback(async (messageId: number): Promise<void> => {
    if (!messageId) return;
    if (readSyncInFlightRef.current.has(messageId)) return;

    readSyncInFlightRef.current.add(messageId);
    try {
      await messagesApi.markAsRead(messageId);
      setMessages((prev) => prev.map((msg) => (
        msg.id === messageId ? { ...msg, is_read: true } : msg
      )));
    } catch (error) {
      logger.warn('[FIX:CHAT] Failed to sync read receipt', { messageId, error });
    } finally {
      readSyncInFlightRef.current.delete(messageId);
    }
  }, []);

  // Обновить количество непрочитанных
  const refreshUnreadCount = useCallback(async (): Promise<void> => {
    if (isBoardRoute || isPublicRoute) return;
    try {
      const count = (await messagesApi.getUnreadCount()) as number | UnreadCountResponse;
      setUnreadCount(typeof count === 'number' ? count : (count?.count ?? 0));
    } catch (error) {
      const err = error as { response?: { status?: number } };
      const status = err?.response?.status;
      if (status === 401 || status === 403) {
        logger.info('[FIX:CHAT] Skipping unread count refresh due to auth state', {
          status,
          path: location.pathname,
        });
        return;
      }
      logger.error('Failed to get unread count:', error);
    }
  }, [isBoardRoute, isPublicRoute, location.pathname]);

  // Обработка сообщения
  const handleNewMessage = useCallback((message: ChatMessage): void => {
    if (isBoardRoute || isPublicRoute) {
      return;
    }

    const currentActive = activeConversationRef.current;
    const activeIdStr = currentActive ? String(currentActive) : null;
    const senderIdStr = String(message.sender_id);
    const recipientIdStr = String(message.recipient_id);
    const currentUserIdStr = user?.id != null ? String(user.id) : null;
    const hasFocus = typeof document?.hasFocus === 'function' ? document.hasFocus() : true;

    const isIncoming = Boolean(activeIdStr && senderIdStr === activeIdStr);
    const isOutgoingSync = Boolean(currentUserIdStr && senderIdStr === currentUserIdStr && activeIdStr && recipientIdStr === activeIdStr);
    const isIncomingForCurrentUser = Boolean(currentUserIdStr && recipientIdStr === currentUserIdStr);
    const isConversationInView = Boolean(
      isIncomingForCurrentUser &&
      isIncoming &&
      isChatOpen &&
      hasFocus
    );

    if (currentActive && (isIncoming || isOutgoingSync)) {
      setMessages((prev) => {
        if (prev.some((m) => m.id === message.id)) return prev;
        return [message, ...prev];
      });
    }

    if (isConversationInView) {
      // Keep sender receipts and unread badge in sync for active viewed conversation.
      void markMessageAsRead(message.id);
    } else {
      void loadConversations({ syncUnread: !isIncomingForCurrentUser });
    }

    // Обновляем счетчик непрочитанных если нужно
    if (isIncomingForCurrentUser && !isConversationInView) {
      setUnreadCount((prev) => prev + 1);

      // Play notification sound ONLY when:
      // 1. Tab is not focused (user is in another tab/window)
      // 2. OR the chat window is closed
      // 3. Never play sound if actively viewing that conversation
      // PR-71: skip sound if conversation is muted
      const isMuted = mutedConversations.has(message.sender_id);
      const shouldPlaySound = (!document.hasFocus() || !isChatOpen) && !isMuted;

      if (shouldPlaySound) {
        try {
          // PR-68 / P0-2: reuse singleton AudioContext to prevent leak
          // (browsers cap ~6 concurrent contexts; was creating one per message)
          if (!chatAudioContextRef.current) {
            const Ctor = (window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext);
            if (!Ctor) {
              throw new Error('AudioContext not supported');
            }
            chatAudioContextRef.current = new Ctor();
          }
          const audioContext = chatAudioContextRef.current;
          // Resume if suspended (browsers auto-suspend after inactivity)
          if (audioContext.state === 'suspended') {
            void audioContext.resume();
          }
          const oscillator = audioContext.createOscillator();
          const gainNode = audioContext.createGain();

          oscillator.connect(gainNode);
          gainNode.connect(audioContext.destination);

          // Pleasant notification tone
          oscillator.frequency.value = 800; // Hz
          oscillator.type = 'sine';

          gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
          gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

          oscillator.start(audioContext.currentTime);
          oscillator.stop(audioContext.currentTime + 0.3);
        } catch {
          // Sound not available
        }
      }

      // Show browser push notification (when tab is not focused)
      pushNotifications.showMessageNotification(
        message,
        message.sender_name || `User ${message.sender_id}`
      );
    }
  }, [isBoardRoute, isPublicRoute, user, loadConversations, isChatOpen, markMessageAsRead, mutedConversations]);

  // Обновляем ref при изменении handleNewMessage
  useEffect(() => {
    handleNewMessageRef.current = handleNewMessage;
  }, [handleNewMessage]);

  // Обновляем ref при изменении loadConversations
  useEffect(() => {
    loadConversationsRef.current = loadConversations;
  }, [loadConversations]);

  const syncChatSnapshot = useCallback(async (): Promise<boolean> => {
    if (!user || isBoardRoute || isPublicRoute) {
      return false;
    }

    const currentUserId = user.id || null;
    if (!currentUserId) {
      return false;
    }

    if (chatSnapshotSyncUserRef.current === currentUserId) {
      return false;
    }

    chatSnapshotSyncUserRef.current = currentUserId;
    await Promise.all([
      loadConversations(),
      refreshUnreadCount(),
    ]);
    return true;
  }, [isBoardRoute, isPublicRoute, loadConversations, refreshUnreadCount, user]);

  // Load the inbox as soon as auth is available, even before WS finishes connecting.
  // This keeps the conversation list usable on slower sockets and on first mount.
  useEffect(() => {
    if (isBoardRoute || isPublicRoute) {
      logger.info('[FIX:CHAT] Chat disabled on board route', { path: location.pathname });
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        try {
          wsRef.current.close(1000, 'Chat disabled on board route');
        } catch (error) {
          logger.warn('[FIX:CHAT] Failed to close chat websocket on board route', error);
        }
        wsRef.current = null;
      }
      resetChatState();
      chatSnapshotSyncUserRef.current = null;
      return () => {};
    }

    const currentUserId = user?.id || null;
    if (!currentUserId) {
      chatSnapshotSyncUserRef.current = null;
      return;
    }

    void syncChatSnapshot();
  }, [isBoardRoute, isPublicRoute, location.pathname, resetChatState, syncChatSnapshot, user?.id]);

  // Request online status of specific users
  const requestOnlineStatus = useCallback((userIds: number[]): void => {
    if (isBoardRoute || isPublicRoute) return;
    if (wsRef.current?.readyState === WebSocket.OPEN && userIds.length > 0) {
      wsRef.current.send(JSON.stringify({
        type: MESSAGE_EVENT_TYPES.GET_ONLINE_STATUS,
        user_ids: userIds,
        contract_version: MESSAGING_CONTRACT_VERSION,
      }));
    }
  }, [isBoardRoute, isPublicRoute]);

  // WebSocket подключение (Один раз на приложение!)
  // Зависит ТОЛЬКО от токена. User и функции исключены для стабильности.
  useEffect(() => {
    if (isBoardRoute || isPublicRoute) {
      return undefined;
    }

    const initialToken = tokenManager.getAccessToken() || token;
    if (!initialToken) return;

    let isMounted = true;
    let activeSocket: WebSocket | null = null;

    const connect = (): void => {
      if (!isMounted) {
        return;
      }

      const latestToken = tokenManager.getAccessToken() || token;
      if (!latestToken) {
        return;
      }

      if (!tokenManager.isTokenValid()) {
        logger.info('[FIX:WS] Chat WebSocket is waiting for a valid auth token');
        reconnectTimeoutRef.current = setTimeout(connect, 1500) as unknown as TimeoutHandle;
        return;
      }

      if (wsRef.current) {
        // Если сокет открыт или соединяется - пропускаем
        if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
          return;
        }
        wsRef.current.close();
      }

      const wsBase = getWsBaseUrl();

      const wsUrl = `${wsBase}/ws/chat`;

      const ws = new WebSocket(wsUrl);
      activeSocket = ws;

      ws.onopen = () => {
        if (!isMounted) {
          ws.close(1000, 'Unmount before open');
          return;
        }
        // F-001: send auth as first message (token no longer in URL)
        ws.send(JSON.stringify({
          type: 'auth',
          token: latestToken,
          contract_version: MESSAGING_CONTRACT_VERSION,
        }));
        setIsConnected(true);
        retryCountRef.current = 0;
        logger.info('[FIX:WS] Chat WebSocket connected (auth via first message)');
        void syncChatSnapshot();
        if (activeConversationRef.current) {
          requestOnlineStatus([activeConversationRef.current]);
        }
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as WsIncomingMessage;
          if (
            data.contract_version &&
            !isSupportedMessagingContractVersion(data.contract_version) &&
            !contractVersionMismatchRef.current
          ) {
            contractVersionMismatchRef.current = true;
            logger.warn('[FIX:WS] Messaging contract version mismatch', {
              expected: MESSAGING_CONTRACT_VERSION,
              received: data.contract_version,
              type: data.type,
            });
          }
          if (data.type === MESSAGE_EVENT_TYPES.NEW_MESSAGE) {
            // Используем ref для вызова актуальной версии функции
            if (data.message && handleNewMessageRef.current) {
              handleNewMessageRef.current(data.message);
            }
          } else if (data.type === MESSAGE_EVENT_TYPES.TYPING) {
            setTypingUsers((prev) => ({ ...prev, [String(data.sender_id)]: data.is_typing }));
          } else if (data.type === MESSAGE_EVENT_TYPES.MESSAGE_READ) {
            const readId = data.message_id;
            setMessages((prev) => prev.map((msg) => msg.id === readId ? { ...msg, is_read: true } : msg));
            loadConversationsRef.current?.();
            void refreshUnreadCount();
          } else if (data.type === MESSAGE_EVENT_TYPES.MESSAGES_READ) {
            const ids = new Set<number>(data.message_ids ?? []);
            setMessages((prev) => prev.map((msg) => ids.has(msg.id) ? { ...msg, is_read: true } : msg));
            loadConversationsRef.current?.();
            void refreshUnreadCount();
          } else if (data.type === MESSAGE_EVENT_TYPES.PING) {
            // Respond to server heartbeat
            ws.send(JSON.stringify({
              type: MESSAGE_EVENT_TYPES.PONG,
              contract_version: MESSAGING_CONTRACT_VERSION,
            }));
          } else if (data.type === MESSAGE_EVENT_TYPES.ONLINE_STATUS) {
            // Update online status of users
            setOnlineUsers((prev) => ({ ...prev, ...(data.users ?? {}) }));
          } else if (data.type === MESSAGE_EVENT_TYPES.REACTION_UPDATE) {
            const reactionMessageId = data.message_id;
            const reactions = data.reactions ?? [];
            setMessages((prev) => prev.map((msg) =>
              msg.id === reactionMessageId ?
              { ...msg, reactions } :
              msg
            ));
          } else if (data.type === MESSAGE_EVENT_TYPES.MESSAGE_DELETED) {
            const deletedId = data.message_id;
            setMessages((prev) => prev.filter((msg) => msg.id !== deletedId));
            loadConversationsRef.current?.();
          }
        } catch (e) {
          logger.error('WS Parse error:', e);
        }
      };

      ws.onclose = (e: CloseEvent) => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        setIsConnected(false);
        setTypingUsers({});
        setOnlineUsers({});
        if (!isMounted) {
          return;
        }
        // F-001: 4001 = auth rejected (invalid/expired token) — don't reconnect with same token
        if (e.code === 4001) {
          logger.warn('[FIX:WS] Chat WebSocket auth rejected (4001), invalidating token');
          // tokenManager may expose invalidateAccessToken() in some builds.
          // Probe via structural cast to avoid coupling this file to the
          // concrete tokenManager implementation.
          const tm = tokenManager as typeof tokenManager & { invalidateAccessToken?: () => void };
          if (tm && typeof tm.invalidateAccessToken === 'function') {
            tm.invalidateAccessToken();
          }
          return;
        }
        // Если не нормальное закрытие (1000) - пробуем переподключиться
        if (e.code !== 1000) {
          // PR-70 / M-1: added jitter to prevent thundering herd on server restart
          const baseDelay = Math.min(1000 * 2 ** retryCountRef.current, 30000);
          const jitter = Math.random() * 500; // 0-500ms random jitter
          const delay = baseDelay + jitter;
          retryCountRef.current += 1;
          logger.info('[FIX:WS] Chat WebSocket closed, scheduling reconnect', {
            code: e.code,
            delay,
          });
          reconnectTimeoutRef.current = setTimeout(connect, delay) as unknown as TimeoutHandle;
        } else {
          retryCountRef.current = 0;
        }
      };

      wsRef.current = ws;
    };

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (activeSocket) {
        if (activeSocket.readyState === WebSocket.OPEN) {
          activeSocket.close(1000, 'Unmount');
        } else if (activeSocket.readyState === WebSocket.CONNECTING) {
          activeSocket.onopen = () => activeSocket?.close(1000, 'Unmount before open');
          activeSocket.onclose = null;
          activeSocket.onerror = null;
          activeSocket.onmessage = null;
        }
      }
    };
  }, [isBoardRoute, isPublicRoute, token, refreshUnreadCount, requestOnlineStatus, syncChatSnapshot]);

  // Загрузка сообщений (при открытии чата)
  const [hasMore, setHasMore] = useState<boolean>(false);

  const loadMessages = useCallback(async (userId: number): Promise<void> => {
    if (!user) return;
    setIsLoading(true);
    try {
      const data = (await messagesApi.getConversation(userId)) as ConversationResponse;
      setMessages(data.messages || []);
      setHasMore(Boolean(data.has_more));

      // Важно: обновляем и ref и state
      activeConversationRef.current = userId;
      setActiveConversation(userId);
      setTypingUsers({});
      setOnlineUsers({});

      // getConversation() already marks the thread as read on the backend.
      // Mirror that locally so opening a chat does not force a full conversations refetch.
      markConversationLocallyRead(userId);
    } catch (e) {
      logger.error('Failed to load messages:', e);
    } finally {
      setIsLoading(false);
    }
  }, [user, markConversationLocallyRead]);

  const loadMoreMessages = useCallback(async (): Promise<void> => {
    const userId = activeConversationRef.current;
    if (!userId || !hasMore || isLoading) return;

    // setIsLoading(true); // Не блокируем весь UI, можно отдельный стейт loadingMore
    try {
      const currentLength = messages.length;
      const data = (await messagesApi.getConversation(userId, currentLength)) as ConversationResponse;

      setMessages((prev) => [...prev, ...(data.messages || [])]);
      setHasMore(Boolean(data.has_more));
    } catch (e) {
      logger.error('Failed to load more messages:', e);
    }
  }, [messages.length, hasMore, isLoading]);

  const sendMessage = useCallback(async (recipientId: number, content: string): Promise<ChatMessage> => {
    const message = (await messagesApi.sendMessage(recipientId, content)) as ChatMessage;
    if (activeConversationRef.current === recipientId) {
      // Проверка на дубликаты - сообщение может прийти через WebSocket раньше
      setMessages((prev) => {
        if (prev.some((m) => m.id === message.id)) return prev;
        return [message, ...prev];
      });
    }
    void loadConversations();
    return message;
  }, [loadConversations]);

  // Закрыть активную беседу
  const closeConversation = useCallback((): void => {
    activeConversationRef.current = null;
    setActiveConversation(null);
    setMessages([]);
    setTypingUsers({});
    setOnlineUsers({});
  }, []);

  // Поиск пользователей
  const searchUsers = useCallback(async (query: string): Promise<AvailableUser[]> => {
    try {
      const result = (await messagesApi.getAvailableUsers(query)) as AvailableUser[] | AvailableUsersResponse;
      if (Array.isArray(result)) {
        return result;
      }
      return result?.users ?? [];
    } catch (error) {
      logger.error('Failed to search users:', error);
      return [];
    }
  }, []);

  // Отправка статуса набора текста
  const sendTyping = useCallback((recipientId: number, isTyping: boolean): void => {
    if (!isBoardRoute && !isPublicRoute && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: MESSAGE_EVENT_TYPES.TYPING,
        recipient_id: recipientId,
        is_typing: isTyping,
        contract_version: MESSAGING_CONTRACT_VERSION,
      }));
    }
  }, [isBoardRoute, isPublicRoute]);

  useEffect(() => {
    setTypingUsers({});
    setOnlineUsers({});
    if (activeConversation) {
      requestOnlineStatus([activeConversation]);
    }
  }, [activeConversation, requestOnlineStatus]);

  // Toggle reaction
  const toggleReaction = useCallback(async (messageId: number, reaction: string): Promise<void> => {
    try {
      await messagesApi.toggleReaction(messageId, reaction);
    } catch (error) {
      logger.error('Failed to toggle reaction:', error);
    }
  }, []);

  // Delete message
  const deleteMessage = useCallback(async (messageId: number): Promise<void> => {
    try {
      await messagesApi.deleteMessage(messageId);
      // WebSocket will handle state update
    } catch (error) {
      logger.error('Failed to delete message:', error);
      throw error;
    }
  }, []);

  // Upload file
  const uploadFile = useCallback(async (recipientId: number, file: File): Promise<ChatMessage> => {
    try {
      const msg = (await messagesApi.uploadFile(recipientId, file)) as ChatMessage;
      // WebSocket will handle state update (new_message)
      return msg;
    } catch (error) {
      logger.error('Failed to upload file:', error);
      throw error;
    }
  }, []);

  const value: ChatContextValue = {
    conversations,
    messages,
    activeConversation,
    unreadCount,
    isConnected,
    isLoading,
    typingUsers,
    isChatOpen,
    setIsChatOpen,
    // PR-71: muted conversations
    mutedConversations,
    setMutedConversations,
    onlineUsers,
    requestOnlineStatus,
    loadConversations,
    loadMessages,
    sendMessage,
    closeConversation,
    setActiveConversation,
    searchUsers,
    sendTyping,
    refreshUnreadCount,
    hasMore,
    loadMoreMessages,
    toggleReaction,
    deleteMessage,
    uploadFile
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );

};

ChatProvider.propTypes = {
  children: PropTypes.node.isRequired
};

export const useChat = (): ChatContextValue => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};
