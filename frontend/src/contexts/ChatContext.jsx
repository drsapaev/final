import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import auth from '../stores/auth';
import * as messagesApi from '../api/messages';

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

    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);
    const activeConversationRef = useRef(activeConversation);

    // Храним актуальные функции в ref
    // Это предотвращает разрыв соединения WebSocket при обновлении функций/стейта
    const handleNewMessageRef = useRef(null);

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
            console.error('Failed to load conversations:', error);
        }
    }, [user]);

    // Обработка сообщения
    const handleNewMessage = useCallback((message) => {
        console.log('🔔 [Context] WS New Message:', message);
        console.log('   Active conversation:', activeConversationRef.current);

        const currentActive = activeConversationRef.current;
        const activeIdStr = currentActive ? String(currentActive) : null;
        const senderIdStr = String(message.sender_id);
        const recipientIdStr = String(message.recipient_id);
        const currentUserIdStr = user ? String(user.id) : null;

        const isIncoming = activeIdStr && senderIdStr === activeIdStr;
        const isOutgoingSync = currentUserIdStr && senderIdStr === currentUserIdStr && activeIdStr && recipientIdStr === activeIdStr;

        if (currentActive && (isIncoming || isOutgoingSync)) {
            console.log('✅ [Context] Adding to active messages');
            setMessages(prev => {
                if (prev.some(m => m.id === message.id)) return prev;
                return [message, ...prev];
            });
        }

        loadConversations(); // Всегда обновляем список

        // Обновляем счетчик непрочитанных если нужно
        if (message.recipient_id === user?.id && (!currentActive || String(currentActive) !== String(message.sender_id))) {
            setUnreadCount(prev => prev + 1);
        }
    }, [user, loadConversations]);

    // Обновляем ref при изменении handleNewMessage
    useEffect(() => {
        handleNewMessageRef.current = handleNewMessage;
    }, [handleNewMessage]);

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
            // Используем VITE_API_URL если задан, иначе VITE_WS_HOST, иначе localhost:8001
            const apiUrl = import.meta.env.VITE_API_URL || '';
            let wsHost = import.meta.env.VITE_WS_HOST;
            if (!wsHost && apiUrl) {
                // Извлекаем host из API URL (http://localhost:8001 -> localhost:8001)
                try {
                    wsHost = new URL(apiUrl).host;
                } catch (e) {
                    wsHost = 'localhost:8001';
                }
            }
            wsHost = wsHost || 'localhost:8001';
            const wsUrl = `${wsProtocol}//${wsHost}/ws/chat?token=${token}`;

            console.log('🔌 [Context] Connecting WS...', wsUrl);
            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                setIsConnected(true);
                console.log('✅ [Context] WS Connected');
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
                        setTypingUsers(prev => ({ ...prev, [data.sender_id]: data.is_typing }));
                    } else if (data.type === 'message_read') {
                        setMessages(prev => prev.map(msg => msg.id === data.message_id ? { ...msg, is_read: true } : msg));
                    }
                } catch (e) {
                    console.error('WS Parse error:', e);
                }
            };

            ws.onclose = (e) => {
                setIsConnected(false);
                // Если не нормальное закрытие (1000) - пробуем переподключиться
                if (e.code !== 1000) {
                    console.log('❌ [Context] WS Disconnected (abnormal), retrying...', e.code);
                    reconnectTimeoutRef.current = setTimeout(connect, 3000);
                } else {
                    console.log('🔒 [Context] WS Closed normally');
                }
            };

            wsRef.current = ws;
        };

        connect();

        return () => {
            if (wsRef.current) {
                console.log('🧹 [Context] Cleaning up WS...');
                wsRef.current.close(1000, "Unmount");
            }
            if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        };
    }, [token]); // <-- Ключевое изменение: только token!

    // Загрузка сообщений (при открытии чата)
    const loadMessages = useCallback(async (userId) => {
        if (!user) return;
        setIsLoading(true);
        try {
            const data = await messagesApi.getConversation(userId);
            setMessages(data.messages || []);

            // Важно: обновляем и ref и state
            activeConversationRef.current = userId;
            setActiveConversation(userId);

            // Сбрасываем непрочитанные
            loadConversations();
        } catch (e) {
            console.error(e);
        } finally {
            setIsLoading(false);
        }
    }, [user, loadConversations]);

    const sendMessage = useCallback(async (recipientId, content) => {
        const message = await messagesApi.sendMessage(recipientId, content);
        if (activeConversationRef.current === recipientId) {
            // Проверка на дубликаты - сообщение может прийти через WebSocket раньше
            setMessages(prev => {
                if (prev.some(m => m.id === message.id)) return prev;
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
            console.error('Failed to search users:', error);
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
            console.error('Failed to get unread count:', error);
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
        loadConversations,
        loadMessages,
        sendMessage,
        closeConversation,
        setActiveConversation,
        searchUsers,
        sendTyping,
        refreshUnreadCount
    };

    return (
        <ChatContext.Provider value={value}>
            {children}
        </ChatContext.Provider>
    );
};

export const useChat = () => {
    const context = useContext(ChatContext);
    if (!context) {
        throw new Error('useChat must be used within a ChatProvider');
    }
    return context;
};
