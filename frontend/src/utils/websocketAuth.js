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
  console.log(`🔌 Создаем аутентифицированное WebSocket соединение: ${wsUrl}`);

  const ws = new WebSocket(wsUrl);

  ws.onopen = (event) => {
    console.log('✅ Аутентифицированное WebSocket подключено');
    if (onConnect) onConnect(event);
  };

  ws.onclose = (event) => {
    console.log('❌ Аутентифицированное WebSocket отключено', event.code, event.reason);
    
    // Обрабатываем ошибки аутентификации
    if (event.code === 1008) { // WS_1008_POLICY_VIOLATION
      console.error('❌ Ошибка аутентификации WebSocket:', event.reason);
      if (onAuthError) {
        onAuthError(event.reason || 'Authentication failed');
      }
    }
    
    if (onDisconnect) onDisconnect(event);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log('📨 Получено сообщение WebSocket:', data);
      
      // Обрабатываем ошибки аутентификации в сообщениях
      if (data.type === 'error' && data.message && data.message.includes('аутентификация')) {
        if (onAuthError) {
          onAuthError(data.message);
        }
      }
      
      if (onMessage) onMessage(data);
    } catch (error) {
      console.warn('⚠️ Ошибка парсинга WebSocket сообщения:', error);
    }
  };

  ws.onerror = (error) => {
    console.error('❌ Ошибка WebSocket:', error);
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
  const baseUrl = `ws://localhost:8000/api/v1/ws-auth/ws/queue/optional-auth`;
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
    console.log('📤 Отправлено аутентифицированное сообщение:', messageWithAuth);
  } else {
    console.warn('⚠️ WebSocket не готов для отправки сообщения');
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
    maxReconnectAttempts = 5,
    reconnectDelay = 3000,
    ...wsOptions
  } = options;

  let ws = null;
  let reconnectTimeout = null;
  let reconnectAttempts = 0;
  let isManuallyDisconnected = false;

  const connect = () => {
    if (isManuallyDisconnected) return;

    try {
      ws = createAuthenticatedWebSocket(baseUrl, params, {
        ...wsOptions,
        onConnect: (event) => {
          console.log('✅ Переподключающийся WebSocket подключен');
          reconnectAttempts = 0;
          if (wsOptions.onConnect) wsOptions.onConnect(event);
        },
        onDisconnect: (event) => {
          console.log('❌ Переподключающийся WebSocket отключен');
          if (wsOptions.onDisconnect) wsOptions.onDisconnect(event);
          
          // Переподключение только если не отключено вручную
          if (!isManuallyDisconnected && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            console.log(`🔄 Попытка переподключения ${reconnectAttempts}/${maxReconnectAttempts}`);
            reconnectTimeout = setTimeout(connect, reconnectDelay);
          }
        },
        onAuthError: (error) => {
          console.error('❌ Ошибка аутентификации, переподключение остановлено:', error);
          isManuallyDisconnected = true; // Останавливаем переподключение при ошибках аутентификации
          if (wsOptions.onAuthError) wsOptions.onAuthError(error);
        }
      });
    } catch (error) {
      console.error('❌ Ошибка создания WebSocket:', error);
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        reconnectTimeout = setTimeout(connect, reconnectDelay);
      }
    }
  };

  const disconnect = () => {
    isManuallyDisconnected = true;
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


