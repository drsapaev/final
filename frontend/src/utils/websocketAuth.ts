import logger from '../utils/logger';
import { buildWsUrl } from '../api/runtime';
import { tokenManager } from '../utils/tokenManager';

interface WebSocketAuthOptions {
  requireAuth?: boolean;
  onAuthError?: (err?: unknown) => void;
  onConnect?: (event?: unknown) => void;
  onDisconnect?: (event?: unknown) => void;
  onMessage?: (event: MessageEvent) => void;
  onError?: (err?: unknown) => void;
  onMaxReconnectAttempts?: () => void;
  maxReconnectAttempts?: number;
  initialReconnectDelay?: number;
  maxReconnectDelay?: number;
  [key: string]: unknown;
}

/**
 * Утилиты для аутентифицированных WebSocket соединений
 */

/**
 * Создает аутентифицированное WebSocket соединение
 * @param {string} baseUrl - Базовый URL WebSocket
 * @param {Object} params - Параметры запроса
 * @param {Object} options - Опции соединения
 * @returns {WebSocket} WebSocket соединение
 */
export function createAuthenticatedWebSocket(baseUrl: string, params: Record<string, string> = {}, options: WebSocketAuthOptions = {}): WebSocket {
  const {
    requireAuth = false,
    onAuthError = null,
    onConnect = null,
    onDisconnect = null,
    onMessage = null,
    onError = null
  } = options;

  const token = tokenManager.getAccessToken();

  // Если требуется аутентификация, но токена нет
  if (requireAuth && !token) {
    if (onAuthError) {
      onAuthError('Требуется аутентификация');
    }
    throw new Error('Authentication required but no token found');
  }

  // PR-36 / P0-3: JWT now sent via Sec-WebSocket-Protocol subprotocol
  // (bearer.<token>) instead of URL query (?token=...). The previous
  // approach leaked the JWT into nginx access logs, browser history,
  // and Referer headers. The backend has supported the subprotocol form
  // since PR-4 (backend). Query params are kept for non-token data only.
  const urlParams = new URLSearchParams(params);

  const wsUrl = `${baseUrl}?${urlParams.toString()}`;
  // Subprotocols are passed as the second argument to WebSocket().
  // The backend extracts the token from the bearer.<token> entry.
  const subprotocols = token ? [`bearer.${token}`] : [];
  logger.log('🔌 Создаем аутентифицированное WebSocket соединение (token via subprotocol)');

  const ws = new WebSocket(wsUrl, subprotocols);

  ws.onopen = (event) => {
    logger.log('✅ Аутентифицированное WebSocket подключено');
    if (onConnect) onConnect(event);
  };

  ws.onclose = (event) => {
    logger.log('❌ Аутентифицированное WebSocket отключено', event.code, event.reason);

    // Обрабатываем ошибки аутентификации
    if (event.code === 1008) {// WS_1008_POLICY_VIOLATION
      logger.error('❌ Ошибка аутентификации WebSocket:', event.reason);
      if (onAuthError) {
        onAuthError(event.reason || 'Authentication failed');
      }
    }

    if (onDisconnect) onDisconnect(event);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      logger.log('📨 Получено сообщение WebSocket:', data);

      // Обрабатываем ошибки аутентификации в сообщениях
      if (data.type === 'error' && data.message && data.message.includes('аутентификация')) {
        if (onAuthError) {
          onAuthError(data.message);
        }
      }

      if (onMessage) onMessage(data);
    } catch (error) {
      logger.warn('⚠️ Ошибка парсинга WebSocket сообщения:', error);
    }
  };

  ws.onerror = (error) => {
    logger.error('❌ Ошибка WebSocket:', error);
    if (onError) onError(error);
  };

  return ws;
}

/**
 * Создает WebSocket для очереди с аутентификацией
 * @param {string} department - Отделение
 * @param {string} date - Дата (YYYY-MM-DD)
 * @param {Object} options - Опции соединения
 * @returns {WebSocket} WebSocket соединение
 */
export function createQueueWebSocket(department: string, date: string, options: WebSocketAuthOptions = {}): WebSocket {
  const baseUrl = buildWsUrl('/api/v1/ws-auth/ws/queue/optional-auth');
  const params = { department, date };

  return createAuthenticatedWebSocket(baseUrl, params, options);
}

/**
 * Создает WebSocket для табло с аутентификацией
 * @param {string} boardId - ID табло
 * @param {Object} options - Опции соединения
 * @returns {WebSocket} WebSocket соединение
 */
export function createDisplayBoardWebSocket(boardId: string, options: WebSocketAuthOptions = {}): WebSocket {
  const baseUrl = buildWsUrl(`/api/v1/display/ws/board/${encodeURIComponent(boardId)}`);
  const params: Record<string, string> = {};

  return createAuthenticatedWebSocket(baseUrl, params, options);
}

/**
 * Отправляет аутентифицированное сообщение через WebSocket
 * @param {WebSocket} ws - WebSocket соединение
 * @param {Object} message - Сообщение для отправки
 */
export function sendAuthenticatedMessage(ws, message) {
  if (ws.readyState === WebSocket.OPEN) {
    const messageWithAuth = {
      ...message,
      timestamp: new Date().toISOString(),
      token: tokenManager.getAccessToken() // Централизованный доступ к токену
    };

    ws.send(JSON.stringify(messageWithAuth));
    logger.log('📤 Отправлено аутентифицированное сообщение:', messageWithAuth);
  } else {
    logger.warn('⚠️ WebSocket не готов для отправки сообщения');
  }
}

/**
 * Создает переподключающийся аутентифицированный WebSocket
 * @param {string} baseUrl - Базовый URL
 * @param {Object} params - Параметры
 * @param {Object} options - Опции
 * @returns {Object} Объект с методами управления соединением
 */
interface ReconnectingWebSocketHandle {
  disconnect: () => void;
  send: (data: unknown) => void;
  readonly readyState: number;
  readonly isConnected: boolean;
}

export function createReconnectingAuthWebSocket(baseUrl: string, params: Record<string, string> = {}, options: WebSocketAuthOptions = {}): ReconnectingWebSocketHandle {
  const {
    maxReconnectAttempts = 10,
    initialReconnectDelay = 1000, // Start with 1 second
    maxReconnectDelay = 30000, // Max 30 seconds
    ...wsOptions
  } = options;

  let ws = null;
  let reconnectTimeout = null;
  let reconnectAttempts = 0;
  let isManuallyDisconnected = false;
  let heartbeatInterval = null;
  let lastPongTime = null;

  // ✅ SECURITY: Exponential backoff calculation
  const getReconnectDelay = (attempt) => {
    const delay = Math.min(
      initialReconnectDelay * Math.pow(2, attempt),
      maxReconnectDelay
    );
    // Add jitter to prevent thundering herd
    const jitter = Math.random() * 0.3 * delay; // Up to 30% jitter
    return delay + jitter;
  };

  const connect = () => {
    if (isManuallyDisconnected) return;

    try {
      ws = createAuthenticatedWebSocket(baseUrl, params, {
        ...wsOptions,
        onConnect: (event) => {
          logger.log('✅ Переподключающийся WebSocket подключен');
          reconnectAttempts = 0;
          lastPongTime = Date.now();

          // ✅ SECURITY: Start heartbeat monitoring
          startHeartbeat();

          if (wsOptions.onConnect) wsOptions.onConnect(event);
        },
        onDisconnect: (event) => {
          logger.log('❌ Переподключающийся WebSocket отключен');
          stopHeartbeat();

          if (wsOptions.onDisconnect) wsOptions.onDisconnect(event);

          // ✅ SECURITY: Exponential backoff reconnection
          if (!isManuallyDisconnected && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            const delay = getReconnectDelay(reconnectAttempts - 1);
            logger.log(`🔄 Попытка переподключения ${reconnectAttempts}/${maxReconnectAttempts} через ${Math.round(delay)}ms`);
            reconnectTimeout = setTimeout(connect, delay);
          } else if (reconnectAttempts >= maxReconnectAttempts) {
            logger.error('❌ Достигнуто максимальное количество попыток переподключения');
            if (wsOptions.onMaxReconnectAttempts) {
              wsOptions.onMaxReconnectAttempts();
            }
          }
        },
        onAuthError: (error) => {
          logger.error('❌ Ошибка аутентификации, переподключение остановлено:', error);
          isManuallyDisconnected = true; // Останавливаем переподключение при ошибках аутентификации
          stopHeartbeat();
          if (wsOptions.onAuthError) wsOptions.onAuthError(error);
        },
        onMessage: (event) => {
          // ✅ SECURITY: Handle heartbeat pong messages
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'ping') {
              // Respond to ping with pong
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'pong', timestamp: Date.now() }));
              }
            } else if (data.type === 'pong') {
              lastPongTime = Date.now();
            }
          } catch {

            // Not JSON, ignore
          }
          if (wsOptions.onMessage) wsOptions.onMessage(event);
        }
      });
    } catch (error) {
      logger.error('❌ Ошибка создания WebSocket:', error);
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        const delay = getReconnectDelay(reconnectAttempts - 1);
        reconnectTimeout = setTimeout(connect, delay);
      }
    }
  };

  // ✅ SECURITY: Heartbeat monitoring
  const startHeartbeat = () => {
    const HEARTBEAT_INTERVAL = 30000; // 30 seconds
    const HEARTBEAT_TIMEOUT = 120000; // 2 minutes

    heartbeatInterval = setInterval(() => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        return;
      }

      // Check if we've received a pong recently
      if (lastPongTime && Date.now() - lastPongTime > HEARTBEAT_TIMEOUT) {
        logger.warn('⚠️ Heartbeat timeout, reconnecting...');
        ws.close();
        return;
      }

      // Send ping
      try {
        ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
      } catch (e) {
        logger.error('Error sending heartbeat ping:', e);
      }
    }, HEARTBEAT_INTERVAL);
  };

  const stopHeartbeat = () => {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
    lastPongTime = null;
  };

  const disconnect = () => {
    isManuallyDisconnected = true;
    stopHeartbeat();
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
  };

  const send = (message) => {
    if (ws) {
      sendAuthenticatedMessage(ws, message);
    }
  };

  // Начинаем подключение
  connect();

  return {
    disconnect,
    send,
    get readyState() {
      return ws ? ws.readyState : WebSocket.CLOSED;
    },
    get isConnected() {
      return ws && ws.readyState === WebSocket.OPEN;
    }
  };
}
