import { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import auth from '../stores/auth';
import * as messagesApi from '../api/messages';
import { pushNotifications } from '../services/pushNotifications';
import logger from '../utils/logger';

const ChatContext = createContext(null);

export const ChatProvider = ({ children }) => {
  const [authState, setAuthState] = useState(auth.getState());
  const user = authState.profile;
  const token = authState.token;

  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [typingUsers, setTypingUsers] = useState({});
  const [isChatOpen, setIsChatOpen] = useState(false); // Track if chat window is open
  const [onlineUsers, setOnlineUsers] = useState({}); // Track online status of users

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const activeConversationRef = useRef(activeConversation);
  const retryCountRef = useRef(0);

  // Храним актуальные функции в ref
  // Это предотвращает разрыв соединения WebSocket при обновлении функций/стейта
  const handleNewMessageRef = useRef(null);
  const loadConversationsRef = useRef(null);

  // Синхронизация ref activeConversation
  useEffect(() => {
    activeConversationRef.current = activeConversation;
  }, [activeConversation]);

  // Подписка на auth
  useEffect(() => {
    const unsubscribe = auth.subscribe(setAuthState);
    return unsubscribe;
  }, []);

  // Загрузка бесед
  const loadConversations = useCallback(async () => {
    if (!user) return;
    try {
      const data = await messagesApi.getConversations();
      setConversations(data.conversations || []);
      setUnreadCount(data.total_unread || 0);
    } catch (error) {
      logger.error('Failed to load conversations:', error);
    }
  }, [user]);

  // Обработка сообщения
  const handleNewMessage = useCallback((message) => {


    const currentActive = activeConversationRef.current;
    const activeIdStr = currentActive ? String(currentActive) : null;
    const senderIdStr = String(message.sender_id);
    const recipientIdStr = String(message.recipient_id);
    const currentUserIdStr = user ? String(user.id) : null;

    const isIncoming = activeIdStr && senderIdStr === activeIdStr;
    const isOutgoingSync = currentUserIdStr && senderIdStr === currentUserIdStr && activeIdStr && recipientIdStr === activeIdStr;

    if (currentActive && (isIncoming || isOutgoingSync)) {

      setMessages((prev) => {
        if (prev.some((m) => m.id === message.id)) return prev;
        return [message, ...prev];
      });
    }

    loadConversations(); // Всегда обновляем список

    // Обновляем счетчик непрочитанных если нужно
    if (message.recipient_id === user?.id && (!currentActive || String(currentActive) !== String(message.sender_id))) {
      setUnreadCount((prev) => prev + 1);

      // Play notification sound ONLY when:
      // 1. Tab is not focused (user is in another tab/window)
      // 2. OR the chat window is closed
      // 3. Never play sound if actively viewing that conversation
      const shouldPlaySound = !document.hasFocus() || !isChatOpen;

      if (shouldPlaySound) {
        try {
          const audioContext = new (window.AudioContext || window.webkitAudioContext)();
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
  }, [user, loadConversations, isChatOpen]);

  // Обновляем ref при изменении handleNewMessage
  useEffect(() => {
    handleNewMessageRef.current = handleNewMessage;
  }, [handleNewMessage]);

  // Обновляем ref при изменении loadConversations
  useEffect(() => {
    loadConversationsRef.current = loadConversations;
  }, [loadConversations]);

  // WebSocket подключение (Один раз на приложение!)
  // Зависит ТОЛЬКО от токена. User и функции исключены для стабильности.
  useEffect(() => {
    if (!token) return;

    const connect = () => {
      if (wsRef.current) {
        // Если сокет открыт или соединяется - пропускаем
        if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
          return;
        }
        wsRef.current.close();
      }

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      // Используем VITE_API_URL если задан, иначе VITE_WS_HOST, иначе localhost:8000
      const apiUrl = import.meta.env.VITE_API_URL || '';
      let wsHost = import.meta.env.VITE_WS_HOST;
      if (!wsHost && apiUrl) {
        // Извлекаем host из API URL (http://localhost:8000 -> localhost:8000)
        try {
          wsHost = new URL(apiUrl).host;
        } catch {
          wsHost = 'localhost:8000';
        }
      }
      wsHost = wsHost || 'localhost:8000';
      const wsUrl = `${wsProtocol}//${wsHost}/ws/chat?token=${token}`;

      // console.log('🔌 [Context] Connecting WS...', wsUrl);
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setIsConnected(true);
        retryCountRef.current = 0;
        // console.log('✅ [Context] WS Connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'new_message') {
            // Используем ref для вызова актуальной версии функции
            if (handleNewMessageRef.current) {
              handleNewMessageRef.current(data.message);
            }
          } else if (data.type === 'typing') {
            setTypingUsers((prev) => ({ ...prev, [data.sender_id]: data.is_typing }));
          } else if (data.type === 'message_read') {
            setMessages((prev) => prev.map((msg) => msg.id === data.message_id ? { ...msg, is_read: true } : msg));
          } else if (data.type === 'messages_read') {
            const ids = new Set(data.message_ids);
            setMessages((prev) => prev.map((msg) => ids.has(msg.id) ? { ...msg, is_read: true } : msg));
          } else if (data.type === 'ping') {
            // Respond to server heartbeat
            ws.send(JSON.stringify({ type: 'pong' }));
          } else if (data.type === 'online_status') {
            // Update online status of users
            // Update online status of users
            setOnlineUsers((prev) => ({ ...prev, ...data.users }));
          } else if (data.type === 'reaction_update') {
            setMessages((prev) => prev.map((msg) =>
            msg.id === data.message_id ?
            { ...msg, reactions: data.reactions } :
            msg
            ));
          } else if (data.type === 'message_deleted') {
            setMessages((prev) => prev.filter((msg) => msg.id !== data.message_id));
            loadConversationsRef.current?.();
          }
        } catch (e) {
          logger.error('WS Parse error:', e);
        }
      };

      ws.onclose = (e) => {
        setIsConnected(false);
        // Если не нормальное закрытие (1000) - пробуем переподключиться
        if (e.code !== 1000) {
          const delay = Math.min(1000 * 2 ** retryCountRef.current, 30000);
          retryCountRef.current += 1;
          // console.log(`❌ [Context] WS Disconnected (abnormal), retrying in ${delay}ms...`, e.code);
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        } else {
          retryCountRef.current = 0;
          // console.log('🔒 [Context] WS Closed normally');
        }
      };

      wsRef.current = ws;
    };

    connect();

    return () => {
      if (wsRef.current) {
        // console.log('🧹 [Context] Cleaning up WS...');
        wsRef.current.close(1000, 'Unmount');
      }
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [token]); // <-- Ключевое изменение: только token!

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

      // Сбрасываем непрочитанные
      loadConversations();
    } catch (e) {
      logger.error('Failed to load messages:', e);
    } finally {
      setIsLoading(false);
    }
  }, [user, loadConversations]);

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
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'typing',
        recipient_id: recipientId,
        is_typing: isTyping
      }));
    }
  }, []);

  // Обновить количество непрочитанных
  const refreshUnreadCount = useCallback(async () => {
    try {
      const count = await messagesApi.getUnreadCount();
      setUnreadCount(count);
    } catch (error) {
      logger.error('Failed to get unread count:', error);
    }
  }, []);

  // Request online status of specific users
  const requestOnlineStatus = useCallback((userIds) => {
    if (wsRef.current?.readyState === WebSocket.OPEN && userIds.length > 0) {
      wsRef.current.send(JSON.stringify({
        type: 'get_online_status',
        user_ids: userIds
      }));
    }
  }, []);

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

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};
