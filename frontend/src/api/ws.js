// Helper для WS с прокси. Управление — VITE_ENABLE_WS=0/1
function wsEnabled() {
  const v = (import.meta?.env?.VITE_ENABLE_WS ?? '0').toString().trim();
  return v === '1' || v.toLowerCase() === 'true';
}

function buildWsBase() {
  const raw = (import.meta?.env?.VITE_WS_BASE ?? '/ws').toString().trim();
  if (/^wss?:\/\//i.test(raw)) return raw.replace(/\/+$/, '');
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = location.host;
  const suffix = raw.startsWith('/') ? raw : `/${raw}`;
  return `${proto}//${host}${suffix}`.replace(/\/+$/, '');
}

/**
 * Открыть WS очереди. onMessage получает уже распарсенный объект.
 * Возвращает функцию close().
 */
export function openQueueWS(department, dateStr, onMessage) {
  if (!wsEnabled()) return () => {};
  let ws = null;

  try {
    const base = buildWsBase();
    const url = `${base}/queue?department=${encodeURIComponent(department)}&date_str=${encodeURIComponent(dateStr)}`;
    ws = new WebSocket(url);
    ws.onmessage = (ev) => {
      try {
        const obj = JSON.parse(ev.data);
        onMessage && onMessage(obj);
      } catch {
        // ignore
      }
    };
    ws.onerror = () => {};
    ws.onclose = () => {};
  } catch {
    // ignore
  }

  return function close() {
    try {
      ws && ws.close(1000, 'bye');
    } catch {
      // Игнорируем ошибки закрытия WebSocket
    }
    ws = null;
  };
}

/**
 * Открыть WebSocket для табло очереди (новая система)
 * Подключается к /api/v1/display/ws/board/{board_id}
 */
export function openDisplayBoardWS(boardId, onMessage, onConnect, onDisconnect) {
  if (!wsEnabled()) return () => {};
  let ws = null;
  let reconnectTimeout = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000;

  function connect() {
    try {
      const base = buildWsBase();
      const token = localStorage.getItem('access_token');
      const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
      const url = `${base}/api/v1/display/ws/board/${encodeURIComponent(boardId)}${tokenParam}`;
      
      console.log(`🔌 Подключаемся к WebSocket: ${url}`);
      
      ws = new WebSocket(url);
      
      ws.onopen = () => {
        console.log(`✅ WebSocket подключен к табло ${boardId}`);
        reconnectAttempts = 0;
        onConnect && onConnect();
        
        // Отправляем ping для поддержания соединения
        const pingInterval = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          } else {
            clearInterval(pingInterval);
          }
        }, 30000);
      };
      
      ws.onmessage = (ev) => {
        try {
          const obj = JSON.parse(ev.data);
          console.log(`📨 Получено WebSocket сообщение:`, obj);
          onMessage && onMessage(obj);
        } catch (e) {
          console.warn('Ошибка парсинга WebSocket сообщения:', e);
        }
      };
      
      ws.onerror = (error) => {
        console.error(`❌ Ошибка WebSocket для табло ${boardId}:`, error);
      };
      
      ws.onclose = (event) => {
        console.log(`🔌 WebSocket закрыт для табло ${boardId}. Код: ${event.code}`);
        onDisconnect && onDisconnect();
        
        // Автоматическое переподключение
        if (reconnectAttempts < maxReconnectAttempts && event.code !== 1000) {
          reconnectAttempts++;
          console.log(`🔄 Попытка переподключения ${reconnectAttempts}/${maxReconnectAttempts} через ${reconnectDelay}ms`);
          
          reconnectTimeout = setTimeout(() => {
            connect();
          }, reconnectDelay);
        }
      };
      
    } catch (error) {
      console.error('Ошибка создания WebSocket:', error);
    }
  }

  // Начальное подключение
  connect();

  return function close() {
    try {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
      
      if (ws) {
        ws.close(1000, 'Закрытие по запросу');
        ws = null;
      }
    } catch (error) {
      console.warn('Ошибка закрытия WebSocket:', error);
    }
  };
}

