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
import { buildWsUrl } from '../api/runtime';
import logger from '../utils/logger';
import { tokenManager } from '../utils/tokenManager';
import { detectPromptInjection } from '../utils/aiValidator';
import {
    MESSAGING_CONTRACT_VERSION,
    isSupportedMessagingContractVersion,
} from '../constants/messagingContract';

/** AI chat session shape. */
interface ChatSession {
    id: string | number;
    title?: string;
    [key: string]: unknown;
}

/** AI chat message shape. */
interface ChatMessage {
    id: string | number;
    role: string;
    content: unknown;
    created_at?: string;
    _pending?: boolean;
    [key: string]: unknown;
}

/** WebSocket message handler shape. */
type WsMessageHandler = ((data: unknown) => void) | null;

/**
 * Хук для AI чата
 * 
 * @param {Object} options
 * @param {boolean} options.useWebSocket - Использовать WebSocket для streaming
 * @param {string} options.contextType - Тип контекста (emr, lab, general)
 * @param {string} options.specialty - Специализация врача
 */
export const useAIChat = (options: Record<string, unknown> = {}) => {
    const {
        useWebSocket = false,
        contextType = 'general',
        specialty = null as unknown
    } = options;

    // State
    const [sessions, setSessions] = useState<ChatSession[]>([]);
    const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [loading, setLoading] = useState(false);
    const [streaming, setStreaming] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [connected, setConnected] = useState(false);

    // Refs
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const handleWebSocketMessageRef = useRef<WsMessageHandler>(null);
    // audit/phase-final, BS-15: shouldReconnect ref + reconnect attempt counter.
    const shouldReconnectRef = useRef(true);
    const reconnectAttemptRef = useRef(0);
    const MAX_RECONNECT_ATTEMPTS = 5;
    const currentSessionRef = useRef<ChatSession | null>(null);
    const loadSessionRequestRef = useRef(0);
    const contractVersionMismatchRef = useRef(false);

    useEffect(() => {
        currentSessionRef.current = currentSession;
    }, [currentSession]);

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
            setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to load sessions');
            return [];
        } finally {
            setLoading(false);
        }
    }, []);

    /**
     * Создать новую сессию
     */
    const createSession = useCallback(async (customContextType: unknown = null, customSpecialty: unknown = null) => {
        try {
            setLoading(true);
            const response = await api.post('/ai/chat/sessions', {
                context_type: customContextType || contextType,
                specialty: customSpecialty || specialty
            });

            const session = response.data;
            setSessions(prev => [session, ...prev]);
            setCurrentSession(session);
            currentSessionRef.current = session;
            setMessages([]);
            setStreaming(false);
            setError(null);

            return session;
        } catch (err) {
            logger.error('Failed to create chat session:', err);
            setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create session');
            return null;
        } finally {
            setLoading(false);
        }
    }, [contextType, specialty]);

    /**
     * Загрузить сессию и её сообщения
     */
    const loadSession = useCallback(async (sessionId: string | number) => {
        const requestId = ++loadSessionRequestRef.current;
        try {
            setLoading(true);
            setError(null);
            setStreaming(false);

            // Загружаем сессию
            const sessionResponse = await api.get(`/ai/chat/sessions/${sessionId}`);
            if (requestId !== loadSessionRequestRef.current) {
                return sessionResponse.data;
            }

            // Загружаем сообщения
            const messagesResponse = await api.get(`/ai/chat/sessions/${sessionId}/messages`);
            if (requestId !== loadSessionRequestRef.current) {
                return sessionResponse.data;
            }

            setCurrentSession(sessionResponse.data);
            currentSessionRef.current = sessionResponse.data;
            setMessages(messagesResponse.data);
            setStreaming(false);
            setError(null);

            return sessionResponse.data;
        } catch (err) {
            logger.error('Failed to load chat session:', err);
            setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to load session');
            return null;
        } finally {
            setLoading(false);
        }
    }, []);

    /**
     * Отправить сообщение (REST)
     */
    const sendMessage = useCallback(async (content: string, includeHistory: boolean = true) => {
        if (!content?.trim()) {
            setError('Message cannot be empty');
            return null;
        }

        // Prompt injection check
        if (detectPromptInjection(content)) {
            setError('Обнаружена попытка prompt injection. Сообщение отклонено.');
            logger.warn('AI chat: prompt injection detected and blocked');
            return null;
        }

        // Создаем сессию если нет
        let sessionId = currentSessionRef.current?.id;
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
            if (currentSessionRef.current?.id !== sessionId) {
                setMessages(prev => prev.filter(m => m.id !== userMessage.id));
                return response.data;
            }
            setMessages(prev => {
                const filtered = prev.filter(m => m.id !== userMessage.id);
                return [...filtered, { ...userMessage, _pending: false }, response.data];
            });

            return response.data;
        } catch (err) {
            logger.error('Failed to send message:', err);
            setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to send message');

            // Откатываем оптимистичное обновление
            setMessages(prev => prev.filter(m => !m._pending));
            return null;
        } finally {
            setLoading(false);
        }
    }, [createSession]);

    /**
     * Удалить сессию
     */
    const deleteSession = useCallback(async (sessionId: string | number) => {
        try {
            await api.delete(`/ai/chat/sessions/${sessionId}`);
            setSessions(prev => prev.filter(s => s.id !== sessionId));

            if (currentSessionRef.current?.id === sessionId) {
                loadSessionRequestRef.current += 1;
                setCurrentSession(null);
                currentSessionRef.current = null;
                setMessages([]);
                setStreaming(false);
                setError(null);
            }

            return true;
        } catch (err) {
            logger.error('Failed to delete session:', err);
            setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete session');
            return false;
        }
    }, []);

    /**
     * Отправить feedback на сообщение
     */
    const sendFeedback = useCallback(async (messageId: string | number, feedbackType: string, comment: unknown = null) => {
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

        // audit/phase-final, BS-15: reset reconnect state on explicit connect.
        shouldReconnectRef.current = true;
        reconnectAttemptRef.current = 0;

        // P0 security fix: JWT sent via Sec-WebSocket-Protocol subprotocol (bearer.<token>)
        // instead of URL query (?token=...). The URL query form leaked the JWT into nginx
        // access logs, browser history, and Referer headers. Backend supports subprotocol
        // auth since PR-4 (backend).
        const wsUrl = `${buildWsUrl('/api/v1/ai/chat/ws')}`;

        try {
            wsRef.current = new WebSocket(wsUrl, [`bearer.${token}`]);

            wsRef.current.onopen = () => {
                logger.info('AI Chat WebSocket connected');
                setConnected(true);
                setError(null);
            };

            wsRef.current.onclose = (event) => {
                logger.info('AI Chat WebSocket closed:', event.code, event.reason);
                setConnected(false);

                // audit/phase-final, BS-15: exponential backoff + max retries.
                if (event.code !== 1000 && event.code !== 4001 && shouldReconnectRef.current) {
                    reconnectAttemptRef.current += 1;
                    if (reconnectAttemptRef.current <= MAX_RECONNECT_ATTEMPTS) {
                        const baseDelay = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current - 1), 16000);
                        const jitter = Math.random() * 500;
                        const delay = baseDelay + jitter;
                        logger.info(`Attempting to reconnect WebSocket (${reconnectAttemptRef.current}/${MAX_RECONNECT_ATTEMPTS}) in ${Math.round(delay)}ms...`);
                        reconnectTimeoutRef.current = setTimeout(() => {
                            if (shouldReconnectRef.current) {
                                connectWebSocket();
                            }
                        }, delay);
                    } else {
                        logger.warn(`WebSocket reconnect giving up after ${MAX_RECONNECT_ATTEMPTS} attempts`);
                    }
                }
            };

            wsRef.current.onerror = (error) => {
                logger.error('AI Chat WebSocket error:', error);
                setError('WebSocket connection failed');
            };

            wsRef.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (
                        data.contract_version &&
                        !isSupportedMessagingContractVersion(data.contract_version) &&
                        !contractVersionMismatchRef.current
                    ) {
                        contractVersionMismatchRef.current = true;
                        logger.warn('AI Chat contract version mismatch', {
                            expected: MESSAGING_CONTRACT_VERSION,
                            received: data.contract_version,
                            type: data.type,
                        });
                    }
                    handleWebSocketMessageRef.current?.(data);
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
    const handleWebSocketMessage = useCallback((data: Record<string, unknown>) => {
        if (
            data.session_id &&
            currentSessionRef.current?.id &&
            data.session_id !== currentSessionRef.current.id &&
            data.type !== 'session'
        ) {
            return;
        }

        switch (data.type) {
            case 'session':
                // Новая сессия создана
                setCurrentSession({ id: data.session_id as string | number });
                currentSessionRef.current = { id: data.session_id as string | number };
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
                            { ...last, content: String(last.content ?? '') + String(data.content ?? '') }
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
                        const updated: ChatMessage = {
                            ...last,
                            id: (data.message_id as string | number) ?? last.id,
                            provider: data.provider,
                            model: data.model,
                            tokens_used: data.tokens,
                            latency_ms: data.latency_ms,
                            was_cached: data.cached,
                            _streaming: false,
                            created_at: new Date().toISOString()
                        };
                        return [
                            ...prev.slice(0, -1),
                            updated
                        ];
                    }
                    return prev;
                });
                break;

            case 'error':
                setStreaming(false);
                setError(String(data.message ?? 'Unknown error'));
                break;

            case 'session_closed':
                if (currentSessionRef.current?.id === data.session_id) {
                    setCurrentSession(null);
                    currentSessionRef.current = null;
                    setMessages([]);
                    setStreaming(false);
                }
                break;

            case 'pong':
                // Keepalive response
                break;

            default:
                logger.warn('Unknown WebSocket message type:', data.type);
        }
    }, []);

    useEffect(() => {
        handleWebSocketMessageRef.current = handleWebSocketMessage as WsMessageHandler;
    }, [handleWebSocketMessage]);

    /**
     * Отправить сообщение через WebSocket
     */
    const sendMessageWS = useCallback((content: string) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            setError('WebSocket not connected');
            return false;
        }

        // Prompt injection check
        if (detectPromptInjection(content)) {
            setError('Обнаружена попытка prompt injection.');
            logger.warn('AI chat WS: prompt injection detected and blocked');
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
            session_id: currentSessionRef.current?.id,
            content,
            context_type: contextType,
            specialty,
            contract_version: MESSAGING_CONTRACT_VERSION
        }));

        return true;
    }, [contextType, specialty]);

    /**
     * Отключиться от WebSocket
     */
    const disconnectWebSocket = useCallback(() => {
        // audit/phase-final, BS-15: set shouldReconnect=false so any in-flight
        // onclose handler won't schedule a reconnect after we close.
        shouldReconnectRef.current = false;

        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
        }

        if (wsRef.current) {
            wsRef.current.onclose = null;
            wsRef.current.onerror = null;
            wsRef.current.onopen = null;
            wsRef.current.onmessage = null;
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
                wsRef.current.send(JSON.stringify({
                    type: 'ping',
                    session_id: currentSessionRef.current?.id,
                    contract_version: MESSAGING_CONTRACT_VERSION
                }));
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
