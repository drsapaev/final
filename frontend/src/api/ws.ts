// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
import { buildWsUrl } from './runtime';

// Helper для WS с прокси. Управление — VITE_ENABLE_WS=0/1
function wsEnabled() {
  const v = (import.meta?.env?.VITE_ENABLE_WS ?? '0').toString().trim();
  return v === '1' || v.toLowerCase() === 'true';
}

/**
 * Открыть WS очереди. onMessage получает уже распарсенный объект.
 * Возвращает функцию close().
 */
export function openQueueWS(department, dateStr, onMessage) {
  if (!wsEnabled()) return () => {};
  let ws = null;

  try {
    const query = `department=${encodeURIComponent(department)}&date_str=${encodeURIComponent(dateStr)}`;
    const url = buildWsUrl(`/ws/queue?${query}`);
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
      // PR-36 / P0-3: JWT now sent via Sec-WebSocket-Protocol subprotocol
      // (bearer.<token>) instead of URL query. Avoids leaking the token
      // into nginx access logs, browser history, and Referer headers.
      const token = tokenManager.getAccessToken();
      const url = buildWsUrl(`/api/v1/display/ws/board/${encodeURIComponent(boardId)}`);
      const subprotocols = token ? [`bearer.${token}`] : [];

      logger.log('🔌 Подключаемся к WebSocket (token via subprotocol)');

      ws = new WebSocket(url, subprotocols);
      
      ws.onopen = () => {
        logger.log(`✅ WebSocket подключен к табло ${boardId}`);
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
          logger.log('📨 Получено WebSocket сообщение:', obj);
          onMessage && onMessage(obj);
        } catch (e) {
          logger.warn('Ошибка парсинга WebSocket сообщения:', e);
        }
      };
      
      ws.onerror = (error) => {
        logger.error(`❌ Ошибка WebSocket для табло ${boardId}:`, error);
      };
      
      ws.onclose = (event) => {
        logger.log(`🔌 WebSocket закрыт для табло ${boardId}. Код: ${event.code}`);
        onDisconnect && onDisconnect();
        
        // Автоматическое переподключение
        if (reconnectAttempts < maxReconnectAttempts && event.code !== 1000) {
          reconnectAttempts++;
          logger.log(`🔄 Попытка переподключения ${reconnectAttempts}/${maxReconnectAttempts} через ${reconnectDelay}ms`);
          
          reconnectTimeout = setTimeout(() => {
            connect();
          }, reconnectDelay);
        }
      };
      
    } catch (error) {
      logger.error('Ошибка создания WebSocket:', error);
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
      logger.warn('Ошибка закрытия WebSocket:', error);
    }
  };
}
