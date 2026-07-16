// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
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

const ChatContext = createContext(null);

export const ChatProvider = ({ children }) => {
  const location = useLocation();
  const [authState, setAuthState] = useState(auth.getState());
  const user = authState.profile;
  const token = authState.token;
  const isBoardRoute = location.pathname.startsWith('/queue-board') || location.pathname.startsWith('/display-board');
  const isPublicRoute = isPublicRoutePath(location.pathname);

  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [typingUsers, setTypingUsers] = useState({});
  const [isChatOpen, setIsChatOpen] = useState(false); // Track if chat window is open
  // PR-71: muted conversations (client-side, no sound/notification for these)
  const [mutedConversations, setMutedConversations] = useState(new Set());
  const [onlineUsers, setOnlineUsers] = useState({}); // Track online status of users

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const activeConversationRef = useRef(activeConversation);
  const retryCountRef = useRef(0);
  const readSyncInFlightRef = useRef(new Set());
  const contractVersionMismatchRef = useRef(false);
  const initialConversationLoadUserRef = useRef(null);
  // PR-68 / P0-2: singleton AudioContext to prevent leak
  const chatAudioContextRef = useRef(null);

  // Храним актуальные функции в ref
  // Это предотвращает разрыв соединения WebSocket при обновлении функций/стейта
  const handleNewMessageRef = useRef(null);
  const loadConversationsRef = useRef(null);
  const chatSnapshotSyncUserRef = useRef(null);

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
    const unsubscribe = auth.subscribe(setAuthState);
    return () => { if (typeof unsubscribe === "function") unsubscribe(); };
  }, []);

  const markConversationLocallyRead = useCallback((userId) => {
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
  const loadConversations = useCallback(async ({ syncUnread = true } = {}) => {
    if (!user || isBoardRoute || isPublicRoute) return;
    try {
      const data = await messagesApi.getConversations();
      setConversations(data.conversations || []);
      if (syncUnread) {
        setUnreadCount(data.total_unread || 0);
      }
    } catch (error) {
      const status = error?.response?.status;
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

  const markMessageAsRead = useCallback(async (messageId) => {
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
  const refreshUnreadCount = useCallback(async () => {
    if (isBoardRoute || isPublicRoute) return;
    try {
      const count = await messagesApi.getUnreadCount();
      setUnreadCount(count);
    } catch (error) {
      const status = error?.response?.status;
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
  const handleNewMessage = useCallback((message) => {
    if (isBoardRoute || isPublicRoute) {
      return;
    }


    const currentActive = activeConversationRef.current;
    const activeIdStr = currentActive ? String(currentActive) : null;
    const senderIdStr = String(message.sender_id);
    const recipientIdStr = String(message.recipient_id);
    const currentUserIdStr = user ? String(user.id) : null;
    const hasFocus = typeof document?.hasFocus === 'function' ? document.hasFocus() : true;

    const isIncoming = activeIdStr && senderIdStr === activeIdStr;
    const isOutgoingSync = currentUserIdStr && senderIdStr === currentUserIdStr && activeIdStr && recipientIdStr === activeIdStr;
    const isIncomingForCurrentUser = currentUserIdStr && recipientIdStr === currentUserIdStr;
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
      loadConversations({ syncUnread: !isIncomingForCurrentUser });
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
            chatAudioContextRef.current = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
          }
          const audioContext = chatAudioContextRef.current;
          // Resume if suspended (browsers auto-suspend after inactivity)
          if (audioContext.state === 'suspended') {
            audioContext.resume();
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
        }}

      // Show browser push notification (when tab is not focused)
      pushNotifications.showMessageNotification(
        message,
        message.sender_name || `User ${message.sender_id}`
      );
    }
  }, [isBoardRoute, isPublicRoute, user, loadConversations, isChatOpen, markMessageAsRead]);

  // Обновляем ref при изменении handleNewMessage
  useEffect(() => {
    handleNewMessageRef.current = handleNewMessage;
  }, [handleNewMessage]);

  // Обновляем ref при изменении loadConversations
  useEffect(() => {
    loadConversationsRef.current = loadConversations;
  }, [loadConversations]);

  const syncChatSnapshot = useCallback(async () => {
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
  const requestOnlineStatus = useCallback((userIds) => {
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
    let activeSocket = null;

    const connect = () => {
      if (!isMounted) {
        return;
      }

      const latestToken = tokenManager.getAccessToken() || token;
      if (!latestToken) {
        return;
      }

      if (!tokenManager.isTokenValid()) {
        logger.info('[FIX:WS] Chat WebSocket is waiting for a valid auth token');
        reconnectTimeoutRef.current = setTimeout(connect, 1500);
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

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
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
            if (handleNewMessageRef.current) {
              handleNewMessageRef.current(data.message);
            }
          } else if (data.type === MESSAGE_EVENT_TYPES.TYPING) {
            setTypingUsers((prev) => ({ ...prev, [data.sender_id]: data.is_typing }));
          } else if (data.type === MESSAGE_EVENT_TYPES.MESSAGE_READ) {
            setMessages((prev) => prev.map((msg) => msg.id === data.message_id ? { ...msg, is_read: true } : msg));
            loadConversationsRef.current?.();
            refreshUnreadCount();
          } else if (data.type === MESSAGE_EVENT_TYPES.MESSAGES_READ) {
            const ids = new Set(data.message_ids);
            setMessages((prev) => prev.map((msg) => ids.has(msg.id) ? { ...msg, is_read: true } : msg));
            loadConversationsRef.current?.();
            refreshUnreadCount();
      } else if (data.type === MESSAGE_EVENT_TYPES.PING) {
        // Respond to server heartbeat
        ws.send(JSON.stringify({
          type: MESSAGE_EVENT_TYPES.PONG,
          contract_version: MESSAGING_CONTRACT_VERSION,
        }));
      } else if (data.type === MESSAGE_EVENT_TYPES.ONLINE_STATUS) {
            // Update online status of users
            // Update online status of users
            setOnlineUsers((prev) => ({ ...prev, ...data.users }));
          } else if (data.type === MESSAGE_EVENT_TYPES.REACTION_UPDATE) {
            setMessages((prev) => prev.map((msg) =>
            msg.id === data.message_id ?
            { ...msg, reactions: data.reactions } :
            msg
            ));
          } else if (data.type === MESSAGE_EVENT_TYPES.MESSAGE_DELETED) {
            setMessages((prev) => prev.filter((msg) => msg.id !== data.message_id));
            loadConversationsRef.current?.();
          }
        } catch (e) {
          logger.error('WS Parse error:', e);
        }
      };

      ws.onclose = (e) => {
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
          logger.warning('[FIX:WS] Chat WebSocket auth rejected (4001), invalidating token');
          if (tokenManager && typeof tokenManager.invalidateAccessToken === 'function') {
            tokenManager.invalidateAccessToken();
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
          reconnectTimeoutRef.current = setTimeout(connect, delay);
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
          activeSocket.onopen = () => activeSocket.close(1000, 'Unmount before open');
          activeSocket.onclose = null;
          activeSocket.onerror = null;
          activeSocket.onmessage = null;
        }
      }
    };
  }, [isBoardRoute, isPublicRoute, token, refreshUnreadCount, requestOnlineStatus]);

  // Загрузка сообщений (при открытии чата)
  const [hasMore, setHasMore] = useState(false);

  const loadMessages = useCallback(async (userId) => {
    if (!user) return;
    setIsLoading(true);
    try {
      const data = await messagesApi.getConversation(userId);
      setMessages(data.messages || []);
      setHasMore(data.has_more);

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

  const loadMoreMessages = useCallback(async () => {
    const userId = activeConversationRef.current;
    if (!userId || !hasMore || isLoading) return;

    // setIsLoading(true); // Не блокируем весь UI, можно отдельный стейт loadingMore
    try {
      const currentLength = messages.length;
      const data = await messagesApi.getConversation(userId, currentLength);

      setMessages((prev) => [...prev, ...(data.messages || [])]);
      setHasMore(data.has_more);
    } catch (e) {
      logger.error('Failed to load more messages:', e);
    }
  }, [messages.length, hasMore, isLoading]);

  const sendMessage = useCallback(async (recipientId, content) => {
    const message = await messagesApi.sendMessage(recipientId, content);
    if (activeConversationRef.current === recipientId) {
      // Проверка на дубликаты - сообщение может прийти через WebSocket раньше
      setMessages((prev) => {
        if (prev.some((m) => m.id === message.id)) return prev;
        return [message, ...prev];
      });
    }
    loadConversations();
    return message;
  }, [loadConversations]);

  // Закрыть активную беседу
  const closeConversation = useCallback(() => {
    activeConversationRef.current = null;
    setActiveConversation(null);
    setMessages([]);
    setTypingUsers({});
    setOnlineUsers({});
  }, []);

  // Поиск пользователей
  const searchUsers = useCallback(async (query) => {
    try {
      return await messagesApi.getAvailableUsers(query);
    } catch (error) {
      logger.error('Failed to search users:', error);
      return [];
    }
  }, []);

  // Отправка статуса набора текста
  const sendTyping = useCallback((recipientId, isTyping) => {
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
  const toggleReaction = useCallback(async (messageId, reaction) => {
    try {
      await messagesApi.toggleReaction(messageId, reaction);
    } catch (error) {
      logger.error('Failed to toggle reaction:', error);
    }
  }, []);

  // Delete message
  const deleteMessage = useCallback(async (messageId) => {
    try {
      await messagesApi.deleteMessage(messageId);
      // WebSocket will handle state update
    } catch (error) {
      logger.error('Failed to delete message:', error);
      throw error;
    }
  }, []);

  // Upload file
  const uploadFile = useCallback(async (recipientId, file) => {
    try {
      const msg = await messagesApi.uploadFile(recipientId, file);
      // WebSocket will handle state update (new_message)
      return msg;
    } catch (error) {
      logger.error('Failed to upload file:', error);
      throw error;
    }
  }, []);

  const value = {
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
        </ChatContext.Provider>);

};

ChatProvider.propTypes = {
  children: PropTypes.node.isRequired
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};
