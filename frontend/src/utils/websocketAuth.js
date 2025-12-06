import logger from '../utils/logger';

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
export function createAuthenticatedWebSocket(baseUrl, params = {}, options = {}) {
  const {
    requireAuth = false,
    onAuthError = null,
    onConnect = null,
    onDisconnect = null,
    onMessage = null,
    onError = null
  } = options;

  const token = localStorage.getItem('access_token');
  
  // Если требуется аутентификация, но токена нет
  if (requireAuth && !token) {
    if (onAuthError) {
      onAuthError('Требуется аутентификация');
    }
    throw new Error('Authentication required but no token found');
  }

  // Добавляем токен к параметрам, если он есть
  const urlParams = new URLSearchParams(params);
  if (token) {
    urlParams.append('token', token);
  }

  const wsUrl = `${baseUrl}?${urlParams.toString()}`;
  logger.log(`🔌 Создаем аутентифицированное WebSocket соединение: ${wsUrl}`);

  const ws = new WebSocket(wsUrl);

  ws.onopen = (event) => {
    logger.log('✅ Аутентифицированное WebSocket подключено');
    if (onConnect) onConnect(event);
  };

  ws.onclose = (event) => {
    logger.log('❌ Аутентифицированное WebSocket отключено', event.code, event.reason);
    
    // Обрабатываем ошибки аутентификации
    if (event.code === 1008) { // WS_1008_POLICY_VIOLATION
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
export function createQueueWebSocket(department, date, options = {}) {
  const baseUrl = 'ws://localhost:8000/api/v1/ws-auth/ws/queue/optional-auth';
  const params = { department, date };
  
  return createAuthenticatedWebSocket(baseUrl, params, options);
}

/**
 * Создает WebSocket для табло с аутентификацией
 * @param {string} boardId - ID табло
 * @param {Object} options - Опции соединения
 * @returns {WebSocket} WebSocket соединение
 */
export function createDisplayBoardWebSocket(boardId, options = {}) {
  const baseUrl = `ws://localhost:8000/api/v1/display/ws/board/${encodeURIComponent(boardId)}`;
  const params = {};
  
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
      token: localStorage.getItem('access_token') // Дополнительная проверка
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
export function createReconnectingAuthWebSocket(baseUrl, params = {}, options = {}) {
  const {
    maxReconnectAttempts = 10,
    initialReconnectDelay = 1000,  // Start with 1 second
    maxReconnectDelay = 30000,     // Max 30 seconds
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
          } catch (e) {
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
    const HEARTBEAT_TIMEOUT = 120000;  // 2 minutes
    
    heartbeatInterval = setInterval(() => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        return;
      }
      
      // Check if we've received a pong recently
      if (lastPongTime && (Date.now() - lastPongTime) > HEARTBEAT_TIMEOUT) {
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


