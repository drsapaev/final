/**
 * useAIChat - React hook для AI чата
 *
 * Функции:
 * - REST API для сессий и сообщений
 * - WebSocket для streaming
 * - Управление состоянием
 *
 * Architecture (ADR-0013 §2):
 * - `sessionState: ChatSessionState` models the WebSocket TRANSPORT layer:
 *   connectionStatus + streamStatus + structured error. It NEVER carries
 *   messages (Invariant 1: transport ≠ content).
 * - `messages`, `currentSession`, `sessions` are separate useState slots —
 *   they have different update patterns and must not be bundled into the
 *   transport state.
 * - `restLoading` / `restError` track REST API operations. They are separate
 *   from `sessionState` because REST is request/response, not streaming.
 * - WebSocket callbacks (`onopen`, `onclose`, `onmessage`) call
 *   `applyConnectionTransition` / `applyStreamTransition` / `setChatError`.
 *   They never mutate `sessionState` directly (Invariant 3: explicit
 *   transitions; Invariant 5: no reducer coupling).
 * - The public return shape is preserved: `loading`, `streaming`, `error`,
 *   `connected` are derived accessors for backward compatibility.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { api } from '../api/client';
import { buildWsUrl } from '../api/runtime';
import logger from '../utils/logger';
import { tokenManager } from '../utils/tokenManager';
import { detectPromptInjection } from '../utils/aiValidator';
import { getErrorMessage } from '../utils/type-guards';
import {
    MESSAGING_CONTRACT_VERSION,
    isSupportedMessagingContractVersion,
} from '../constants/messagingContract';
import type {
    ChatSessionState,
    ChatError,
    ChatErrorCode,
} from '../types/chat-session-state';
import {
    idleChatSessionState,
    applyConnectionTransition,
    applyStreamTransition,
    setChatError,
    incrementReconnectAttempt,
    isChatConnecting,
    isChatConnected,
    isChatStreaming,
    getChatErrorMessage,
    chatError,
} from '../types/chat-session-state';

/** AI chat session shape. */
interface ChatSession {
    id: string | number;
    title?: string;
    [key: string]: unknown;
}

// TECH-DEBT(g8-useAIChat-001): AIAssistantMsg is a local shape for the AI
// assistant chat. The canonical domain ChatMessage (types/domain/chat.ts)
// is for 1:1 staff messaging (sender_id/recipient_id required, id: number).
// AI chat uses role-based messages (user/assistant/system) with string|number
// ids and _pending flags for optimistic UI. These will converge when the AI
// chat subsystem gets its own domain type.
interface AIAssistantMsg {
    id: string | number;
    role: string;
    content: unknown;
    created_at?: string;
    _pending?: boolean;
    _streaming?: boolean;
    [key: string]: unknown;
}

/** WebSocket message handler shape. */
type WsMessageHandler = ((data: unknown) => void) | null;

/** Maximum WebSocket reconnect attempts before giving up. */
const MAX_RECONNECT_ATTEMPTS = 5;

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

    // ======================================================================
    // State
    //
    // Three independent slots per ADR-0013 §2:
    //   1. sessionState  — WebSocket transport (connection + stream + WS error)
    //   2. messages      — chat content (separate from transport, Invariant 1)
    //   3. restLoading / restError — REST API request/response state
    //
    // Plus session/bookkeeping UI state that has no async lifecycle.
    // ======================================================================

    const [sessionState, setSessionState] = useState<ChatSessionState>(idleChatSessionState);
    const [sessions, setSessions] = useState<ChatSession[]>([]);
    const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
    const [messages, setMessages] = useState<AIAssistantMsg[]>([]);
    const [restLoading, setRestLoading] = useState(false);
    const [restError, setRestError] = useState<string | null>(null);

    // Refs (mirror of state used inside async / WS callbacks)
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const handleWebSocketMessageRef = useRef<WsMessageHandler>(null);
    // audit/phase-final, BS-15: shouldReconnect ref + reconnect attempt counter.
    const shouldReconnectRef = useRef(true);
    const currentSessionRef = useRef<ChatSession | null>(null);
    const loadSessionRequestRef = useRef(0);
    const contractVersionMismatchRef = useRef(false);

    useEffect(() => {
        currentSessionRef.current = currentSession;
    }, [currentSession]);

    // ======================================================================
    // REST API Methods
    //
    // REST calls update `messages`, `currentSession`, `restLoading`,
    // `restError`. They DO NOT touch `sessionState` — REST is request/response,
    // not streaming. (The only exception: a REST load may cancel an in-flight
    // stream by transitioning streamStatus → idle.)
    // ======================================================================

    /**
     * Загрузить список сессий
     */
    const loadSessions = useCallback(async (limit = 20) => {
        try {
            setRestLoading(true);
            const response = await api.get('/ai/chat/sessions', { params: { limit } });
            setSessions(response.data);
            return response.data;
        } catch (err) {
            logger.error('Failed to load chat sessions:', err);
            setRestError(getErrorMessage(err) || 'Failed to load sessions');
            return [];
        } finally {
            setRestLoading(false);
        }
    }, []);

    /**
     * Создать новую сессию
     */
    const createSession = useCallback(async (customContextType: unknown = null, customSpecialty: unknown = null) => {
        try {
            setRestLoading(true);
            const response = await api.post('/ai/chat/sessions', {
                context_type: customContextType || contextType,
                specialty: customSpecialty || specialty
            });

            const session = response.data;
            setSessions(prev => [session, ...prev]);
            setCurrentSession(session);
            currentSessionRef.current = session;
            setMessages([]);
            // Cancel any in-flight stream from a previous session.
            // (completed → idle is allowed; streaming → idle is allowed; idle → idle is idempotent.)
            setSessionState(prev => applyStreamTransition(prev, 'idle', { clearError: true }));
            setRestError(null);

            return session;
        } catch (err) {
            logger.error('Failed to create chat session:', err);
            setRestError(getErrorMessage(err) || 'Failed to create session');
            return null;
        } finally {
            setRestLoading(false);
        }
    }, [contextType, specialty]);

    /**
     * Загрузить сессию и её сообщения
     */
    const loadSession = useCallback(async (sessionId: string | number) => {
        const requestId = ++loadSessionRequestRef.current;
        try {
            setRestLoading(true);
            setRestError(null);
            // Cancel any in-flight stream when loading a different session.
            setSessionState(prev => applyStreamTransition(prev, 'idle'));

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
            setSessionState(prev => applyStreamTransition(prev, 'idle'));
            setRestError(null);

            return sessionResponse.data;
        } catch (err) {
            logger.error('Failed to load chat session:', err);
            setRestError(getErrorMessage(err) || 'Failed to load session');
            return null;
        } finally {
            setRestLoading(false);
        }
    }, []);

    /**
     * Отправить сообщение (REST)
     */
    const sendMessage = useCallback(async (content: string, includeHistory: boolean = true) => {
        if (!content?.trim()) {
            setRestError('Message cannot be empty');
            return null;
        }

        // Prompt injection check
        if (detectPromptInjection(content)) {
            setRestError('Обнаружена попытка prompt injection. Сообщение отклонено.');
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
            setRestLoading(true);
            setRestError(null);

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
            setRestError(getErrorMessage(err) || 'Failed to send message');

            // Откатываем оптимистичное обновление
            setMessages(prev => prev.filter(m => !m._pending));
            return null;
        } finally {
            setRestLoading(false);
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
                setSessionState(prev => applyStreamTransition(prev, 'idle', { clearError: true }));
                setRestError(null);
            }

            return true;
        } catch (err) {
            logger.error('Failed to delete session:', err);
            setRestError(getErrorMessage(err) || 'Failed to delete session');
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

    // ======================================================================
    // WebSocket Methods
    //
    // WS callbacks update `sessionState` via the transition helpers. They
    // never assign to `sessionState` directly. (Invariant 3 + Invariant 5.)
    // ======================================================================

    /**
     * Подключиться к WebSocket
     */
    const connectWebSocket = useCallback(() => {
        if (!useWebSocket) return;

        const token = tokenManager.getAccessToken();
        if (!token) {
            setSessionState(prev =>
                setChatError(prev, chatError('auth_error', 'Not authenticated', false))
            );
            return;
        }

        // audit/phase-final, BS-15: reset reconnect state on explicit connect.
        shouldReconnectRef.current = true;

        // Transition idle/disconnected/reconnecting → connecting.
        // (connected → connecting is also allowed: explicit reconnect.)
        setSessionState(prev =>
            applyConnectionTransition(prev, 'connecting', { resetReconnectAttempt: true })
        );

        // P0 security fix: JWT sent via Sec-WebSocket-Protocol subprotocol (bearer.<token>)
        // instead of URL query (?token=...). The URL query form leaked the JWT into nginx
        // access logs, browser history, and Referer headers. Backend supports subprotocol
        // auth since PR-4 (backend).
        const wsUrl = `${buildWsUrl('/api/v1/ai/chat/ws')}`;

        try {
            wsRef.current = new WebSocket(wsUrl, [`bearer.${token}`]);

            wsRef.current.onopen = () => {
                logger.info('AI Chat WebSocket connected');
                // connecting → connected (clears any prior error, resets reconnect attempt).
                setSessionState(prev =>
                    applyConnectionTransition(prev, 'connected', {
                        clearError: true,
                        resetReconnectAttempt: true,
                    })
                );
            };

            wsRef.current.onclose = (event) => {
                logger.info('AI Chat WebSocket closed:', event.code, event.reason);

                // Decide next connection state based on close code + shouldReconnect flag.
                // Code 1000 (normal) and 4001 (policy) are treated as terminal → disconnected.
                // Anything else with shouldReconnect=true → reconnecting (will retry).
                const isNormalClose = event.code === 1000 || event.code === 4001;
                if (isNormalClose || !shouldReconnectRef.current) {
                    setSessionState(prev =>
                        applyConnectionTransition(prev, 'disconnected')
                    );
                    return;
                }

                // Schedule reconnect with exponential backoff + jitter.
                setSessionState(prev => {
                    const next = incrementReconnectAttempt(prev);
                    if (next.reconnectAttempt > MAX_RECONNECT_ATTEMPTS) {
                        logger.warn(
                            `WebSocket reconnect giving up after ${MAX_RECONNECT_ATTEMPTS} attempts`
                        );
                        return applyConnectionTransition(
                            setChatError(
                                prev,
                                chatError(
                                    'network_error',
                                    `Connection lost after ${MAX_RECONNECT_ATTEMPTS} reconnect attempts`,
                                    false
                                )
                            ),
                            'disconnected'
                        );
                    }
                    const baseDelay = Math.min(
                        1000 * Math.pow(2, next.reconnectAttempt - 1),
                        16000
                    );
                    const jitter = Math.random() * 500;
                    const delay = baseDelay + jitter;
                    logger.info(
                        `Attempting to reconnect WebSocket (${next.reconnectAttempt}/${MAX_RECONNECT_ATTEMPTS}) in ${Math.round(delay)}ms...`
                    );
                    reconnectTimeoutRef.current = setTimeout(() => {
                        if (shouldReconnectRef.current) {
                            connectWebSocket();
                        }
                    }, delay);
                    return applyConnectionTransition(next, 'reconnecting');
                });
            };

            wsRef.current.onerror = (error) => {
                logger.error('AI Chat WebSocket error:', error);
                // Note: onerror is usually followed by onclose, which handles
                // reconnect logic. We only surface the structured error here.
                setSessionState(prev =>
                    setChatError(
                        prev,
                        chatError('network_error', 'WebSocket connection failed', true)
                    )
                );
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
            setSessionState(prev =>
                setChatError(
                    prev,
                    chatError('network_error', 'Failed to connect to chat', true)
                )
            );
        }
    }, [useWebSocket]);

    /**
     * Обработка WebSocket сообщений.
     *
     * This callback updates `sessionState.streamStatus` and `messages`.
     * It does NOT touch `connectionStatus` — that is owned by the WS
     * connection handlers above. (Invariant 4: two independent dimensions.)
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

        // Map backend error `type` field to a structured ChatErrorCode.
        // The backend currently sends only a free-form `message`; we infer
        // the code from common substrings. This is intentionally conservative.
        const inferErrorCode = (raw: unknown): { code: ChatErrorCode; retryable: boolean } => {
            const msg = String(raw ?? '').toLowerCase();
            if (msg.includes('rate') && msg.includes('limit')) return { code: 'rate_limit', retryable: true };
            if (msg.includes('auth') || msg.includes('token')) return { code: 'auth_error', retryable: false };
            if (msg.includes('cancel')) return { code: 'cancelled', retryable: false };
            if (msg.includes('quota')) return { code: 'rate_limit', retryable: true };
            return { code: 'model_error', retryable: true };
        };

        switch (data.type) {
            case 'session':
                // Новая сессия создана
                setCurrentSession({ id: data.session_id as string | number });
                currentSessionRef.current = { id: data.session_id as string | number };
                break;

            case 'chunk':
                // Streaming chunk — transition streamStatus → streaming (idempotent).
                setSessionState(prev =>
                    applyStreamTransition(prev, 'streaming', { clearError: true })
                );
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
                // Streaming завершен — transition streaming → completed.
                setSessionState(prev => applyStreamTransition(prev, 'completed'));
                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last?._streaming) {
                        const updated: AIAssistantMsg = {
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

            case 'error': {
                // Backend reported an error during streaming.
                const message = String(data.message ?? 'Unknown error');
                const { code, retryable } = inferErrorCode(data.message);
                const chatErr: ChatError = chatError(code, message, retryable);
                setSessionState(prev => {
                    // streaming → idle (cancel any in-flight stream), then attach error.
                    const transitioned = applyStreamTransition(prev, 'idle');
                    return setChatError(transitioned, chatErr);
                });
                break;
            }

            case 'session_closed':
                if (currentSessionRef.current?.id === data.session_id) {
                    setCurrentSession(null);
                    currentSessionRef.current = null;
                    setMessages([]);
                    // completed/streaming → idle is allowed; idle → idle is idempotent.
                    setSessionState(prev => applyStreamTransition(prev, 'idle'));
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
        handleWebSocketMessageRef.current = handleWebSocketMessage as unknown as WsMessageHandler;
    }, [handleWebSocketMessage]);

    /**
     * Отправить сообщение через WebSocket
     */
    const sendMessageWS = useCallback((content: string) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            setSessionState(prev =>
                setChatError(prev, chatError('network_error', 'WebSocket not connected', true))
            );
            return false;
        }

        // Prompt injection check
        if (detectPromptInjection(content)) {
            setSessionState(prev =>
                setChatError(prev, chatError('cancelled', 'Обнаружена попытка prompt injection.', false))
            );
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

        // connected/reconnecting/connecting → disconnected (terminal).
        setSessionState(prev => applyConnectionTransition(prev, 'disconnected'));
    }, []);

    // ======================================================================
    // Effects
    // ======================================================================

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
        if (!useWebSocket || !isChatConnected(sessionState)) return;

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
    }, [useWebSocket, sessionState]);

    // ======================================================================
    // Return — backward-compatible public API
    //
    // Legacy boolean fields are derived from `sessionState`:
    //   loading   ← restLoading (REST API only)
    //   streaming ← isChatStreaming(sessionState)
    //   connected ← isChatConnected(sessionState)
    //   error     ← restError ?? getChatErrorMessage(sessionState)
    // ======================================================================

    const clearError = useCallback(() => {
        setRestError(null);
        setSessionState(prev => setChatError(prev, null));
    }, []);

    return {
        // State (legacy field names preserved for backward compatibility)
        sessions,
        currentSession,
        messages,
        loading: restLoading,
        streaming: isChatStreaming(sessionState),
        error: restError ?? getChatErrorMessage(sessionState),
        connected: isChatConnected(sessionState),

        // Expose the structured transport state for advanced consumers
        // (e.g. UI that wants to distinguish 'reconnecting' from 'connecting').
        sessionState,

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
        clearError,
        clearMessages: () => setMessages([]),
        setCurrentSession,
    };
};

export default useAIChat;
