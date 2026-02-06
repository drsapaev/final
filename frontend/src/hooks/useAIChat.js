/**
 * useAIChat - React hook для AI чата
 * 
 * Функции:
 * - REST API для сессий и сообщений
 * - WebSocket для streaming
 * - Управление состоянием
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { api } from '../api/client';
import logger from '../utils/logger';
import { tokenManager } from '../utils/tokenManager';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

/**
 * Хук для AI чата
 * 
 * @param {Object} options
 * @param {boolean} options.useWebSocket - Использовать WebSocket для streaming
 * @param {string} options.contextType - Тип контекста (emr, lab, general)
 * @param {string} options.specialty - Специализация врача
 */
export const useAIChat = (options = {}) => {
    const {
        useWebSocket = false,
        contextType = 'general',
        specialty = null
    } = options;

    // State
    const [sessions, setSessions] = useState([]);
    const [currentSession, setCurrentSession] = useState(null);
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(false);
    const [streaming, setStreaming] = useState(false);
    const [error, setError] = useState(null);
    const [connected, setConnected] = useState(false);

    // Refs
    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);

    // ==========================================================================
    // REST API Methods
    // ==========================================================================

    /**
     * Загрузить список сессий
     */
    const loadSessions = useCallback(async (limit = 20) => {
        try {
            setLoading(true);
            const response = await api.get('/ai/chat/sessions', { params: { limit } });
            setSessions(response.data);
            return response.data;
        } catch (err) {
            logger.error('Failed to load chat sessions:', err);
            setError(err.response?.data?.detail || 'Failed to load sessions');
            return [];
        } finally {
            setLoading(false);
        }
    }, []);

    /**
     * Создать новую сессию
     */
    const createSession = useCallback(async (customContextType = null, customSpecialty = null) => {
        try {
            setLoading(true);
            const response = await api.post('/ai/chat/sessions', {
                context_type: customContextType || contextType,
                specialty: customSpecialty || specialty
            });

            const session = response.data;
            setSessions(prev => [session, ...prev]);
            setCurrentSession(session);
            setMessages([]);

            return session;
        } catch (err) {
            logger.error('Failed to create chat session:', err);
            setError(err.response?.data?.detail || 'Failed to create session');
            return null;
        } finally {
            setLoading(false);
        }
    }, [contextType, specialty]);

    /**
     * Загрузить сессию и её сообщения
     */
    const loadSession = useCallback(async (sessionId) => {
        try {
            setLoading(true);

            // Загружаем сессию
            const sessionResponse = await api.get(`/ai/chat/sessions/${sessionId}`);
            setCurrentSession(sessionResponse.data);

            // Загружаем сообщения
            const messagesResponse = await api.get(`/ai/chat/sessions/${sessionId}/messages`);
            setMessages(messagesResponse.data);

            return sessionResponse.data;
        } catch (err) {
            logger.error('Failed to load chat session:', err);
            setError(err.response?.data?.detail || 'Failed to load session');
            return null;
        } finally {
            setLoading(false);
        }
    }, []);

    /**
     * Отправить сообщение (REST)
     */
    const sendMessage = useCallback(async (content, includeHistory = true) => {
        if (!content?.trim()) {
            setError('Message cannot be empty');
            return null;
        }

        // Создаем сессию если нет
        let sessionId = currentSession?.id;
        if (!sessionId) {
            const session = await createSession();
            if (!session) return null;
            sessionId = session.id;
        }

        try {
            setLoading(true);
            setError(null);

            // Оптимистично добавляем user message
            const userMessage = {
                id: Date.now(),
                role: 'user',
                content,
                created_at: new Date().toISOString(),
                _pending: true
            };
            setMessages(prev => [...prev, userMessage]);

            // Отправляем запрос
            const response = await api.post(`/ai/chat/sessions/${sessionId}/messages`, {
                content,
                include_history: includeHistory
            });

            // Обновляем сообщения
            setMessages(prev => {
                const filtered = prev.filter(m => m.id !== userMessage.id);
                return [...filtered, { ...userMessage, _pending: false }, response.data];
            });

            return response.data;
        } catch (err) {
            logger.error('Failed to send message:', err);
            setError(err.response?.data?.detail || 'Failed to send message');

            // Откатываем оптимистичное обновление
            setMessages(prev => prev.filter(m => !m._pending));
            return null;
        } finally {
            setLoading(false);
        }
    }, [currentSession, createSession]);

    /**
     * Удалить сессию
     */
    const deleteSession = useCallback(async (sessionId) => {
        try {
            await api.delete(`/ai/chat/sessions/${sessionId}`);
            setSessions(prev => prev.filter(s => s.id !== sessionId));

            if (currentSession?.id === sessionId) {
                setCurrentSession(null);
                setMessages([]);
            }

            return true;
        } catch (err) {
            logger.error('Failed to delete session:', err);
            setError(err.response?.data?.detail || 'Failed to delete session');
            return false;
        }
    }, [currentSession]);

    /**
     * Отправить feedback на сообщение
     */
    const sendFeedback = useCallback(async (messageId, feedbackType, comment = null) => {
        try {
            await api.post(`/ai/chat/messages/${messageId}/feedback`, {
                feedback_type: feedbackType,
                comment
            });
            return true;
        } catch (err) {
            logger.error('Failed to send feedback:', err);
            return false;
        }
    }, []);

    // ==========================================================================
    // WebSocket Methods
    // ==========================================================================

    /**
     * Подключиться к WebSocket
     */
    const connectWebSocket = useCallback(() => {
        if (!useWebSocket) return;

        const token = tokenManager.getAccessToken();
        if (!token) {
            setError('Not authenticated');
            return;
        }

        const wsUrl = `${WS_BASE_URL}/api/v1/ai/chat/ws?token=${token}`;

        try {
            wsRef.current = new WebSocket(wsUrl);

            wsRef.current.onopen = () => {
                logger.info('AI Chat WebSocket connected');
                setConnected(true);
                setError(null);
            };

            wsRef.current.onclose = (event) => {
                logger.info('AI Chat WebSocket closed:', event.code, event.reason);
                setConnected(false);

                // Reconnect after 3 seconds (если не был явный logout)
                if (event.code !== 1000 && event.code !== 4001) {
                    reconnectTimeoutRef.current = setTimeout(() => {
                        logger.info('Attempting to reconnect WebSocket...');
                        connectWebSocket();
                    }, 3000);
                }
            };

            wsRef.current.onerror = (error) => {
                logger.error('AI Chat WebSocket error:', error);
                setError('WebSocket connection failed');
            };

            wsRef.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleWebSocketMessage(data);
                } catch (err) {
                    logger.error('Failed to parse WebSocket message:', err);
                }
            };
        } catch (err) {
            logger.error('Failed to create WebSocket:', err);
            setError('Failed to connect to chat');
        }
    }, [useWebSocket]);

    /**
     * Обработка WebSocket сообщений
     */
    const handleWebSocketMessage = useCallback((data) => {
        switch (data.type) {
            case 'session':
                // Новая сессия создана
                setCurrentSession({ id: data.session_id });
                break;

            case 'chunk':
                // Streaming chunk
                setStreaming(true);
                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last?.role === 'assistant' && last._streaming) {
                        // Добавляем к текущему streaming сообщению
                        return [
                            ...prev.slice(0, -1),
                            { ...last, content: last.content + data.content }
                        ];
                    } else {
                        // Создаем новое streaming сообщение
                        return [
                            ...prev,
                            {
                                id: Date.now(),
                                role: 'assistant',
                                content: data.content,
                                _streaming: true
                            }
                        ];
                    }
                });
                break;

            case 'done':
                // Streaming завершен
                setStreaming(false);
                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last?._streaming) {
                        return [
                            ...prev.slice(0, -1),
                            {
                                ...last,
                                id: data.message_id,
                                provider: data.provider,
                                model: data.model,
                                tokens_used: data.tokens,
                                latency_ms: data.latency_ms,
                                was_cached: data.cached,
                                _streaming: false,
                                created_at: new Date().toISOString()
                            }
                        ];
                    }
                    return prev;
                });
                break;

            case 'error':
                setStreaming(false);
                setError(data.message);
                break;

            case 'pong':
                // Keepalive response
                break;

            default:
                logger.warn('Unknown WebSocket message type:', data.type);
        }
    }, []);

    /**
     * Отправить сообщение через WebSocket
     */
    const sendMessageWS = useCallback((content) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            setError('WebSocket not connected');
            return false;
        }

        // Добавляем user message
        setMessages(prev => [
            ...prev,
            {
                id: Date.now(),
                role: 'user',
                content,
                created_at: new Date().toISOString()
            }
        ]);

        // Отправляем
        wsRef.current.send(JSON.stringify({
            type: 'message',
            session_id: currentSession?.id,
            content,
            context_type: contextType,
            specialty
        }));

        return true;
    }, [currentSession, contextType, specialty]);

    /**
     * Отключиться от WebSocket
     */
    const disconnectWebSocket = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
        }

        if (wsRef.current) {
            wsRef.current.close(1000, 'User disconnect');
            wsRef.current = null;
        }

        setConnected(false);
    }, []);

    // ==========================================================================
    // Effects
    // ==========================================================================

    // Подключаемся к WebSocket при монтировании (если включено)
    useEffect(() => {
        if (useWebSocket) {
            connectWebSocket();
        }

        return () => {
            disconnectWebSocket();
        };
    }, [useWebSocket, connectWebSocket, disconnectWebSocket]);

    // Ping каждые 30 секунд для keepalive
    useEffect(() => {
        if (!useWebSocket || !connected) return;

        const interval = setInterval(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);

        return () => clearInterval(interval);
    }, [useWebSocket, connected]);

    // ==========================================================================
    // Return
    // ==========================================================================

    return {
        // State
        sessions,
        currentSession,
        messages,
        loading,
        streaming,
        error,
        connected,

        // REST methods
        loadSessions,
        createSession,
        loadSession,
        sendMessage,
        deleteSession,
        sendFeedback,

        // WebSocket methods
        connectWebSocket,
        disconnectWebSocket,
        sendMessageWS: useWebSocket ? sendMessageWS : sendMessage,

        // Utilities
        clearError: () => setError(null),
        clearMessages: () => setMessages([]),
        setCurrentSession,
    };
};

export default useAIChat;
