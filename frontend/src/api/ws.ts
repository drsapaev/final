import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
import { buildWsUrl } from './runtime';
import { safeJsonParse } from '../utils/safeJsonParse';

// Helper для WS с прокси. Управление — VITE_ENABLE_WS=0/1
function wsEnabled() {
  const v = (import.meta?.env?.VITE_ENABLE_WS ?? '0').toString().trim();
  return v === '1' || v.toLowerCase() === 'true';
}

/**
 * Открыть WS очереди. onMessage получает уже распарсенный объект.
 * Возвращает функцию close().
 */
export function openQueueWS(department: string, dateStr: string, onMessage: (data: unknown) => void): () => void {
  if (!wsEnabled()) return () => {};
  let ws: WebSocket | null = null;

  try {
    const query = `department=${encodeURIComponent(department)}&date_str=${encodeURIComponent(dateStr)}`;
    const url = buildWsUrl(`/ws/queue?${query}`);
    ws = new WebSocket(url);
    ws.onmessage = (ev) => {
      try {
        const obj = safeJsonParse(ev.data);
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
export function openDisplayBoardWS(boardId: string, onMessage: (data: unknown) => void, onConnect: () => void, onDisconnect: () => void): () => void {
  if (!wsEnabled()) return () => {};
  let ws: WebSocket | null = null;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  // audit/phase-4, BS-14: hoist `pingIntervalRef` to outer scope so `close()`
  // and `ws.onclose` can clear it. Previously `pingInterval` was declared
  // inside `ws.onopen` (local closure), so:
  //   - `close()` had no reference to it → could not clear → interval kept
  //     firing every 30s forever after close (and after every reconnect a
  //     NEW interval stacked on top of the old one — up to 5 leaks per
  //     board mount on flaky networks).
  //   - The `else { clearInterval(pingInterval); }` branch only fired when
  //     readyState !== OPEN, which is exactly when the socket is already
  //     closing — too late to prevent the leak.
  // The ref-based approach guarantees a single live interval at any time.
  let pingIntervalRef: ReturnType<typeof setInterval> | null = null;
  // DISPLAYWS-FE-004 (audit PR #3961): публичное ТВ-табло обязано
  // восстанавливаться после длительного сбоя сети/бэкенда. Лимит в 5
  // попыток оставлял киоск отключённым до remount/перезагрузки страницы.
  // Теперь попытки бесконечны, но с ОГРАНИЧЕННЫМ экспоненциальным backoff
  // (capped 30s) и джиттером — нет ни перманентного обрыва, ни тугого
  // бесконечного цикла. Ручное закрытие (code 1000/close()) по-прежнему
  // останавливает реконнект.
  let reconnectAttempts = 0;
  const reconnectBaseDelayMs = 3000;
  const maxReconnectDelayMs = 30000;

  function clearPingInterval() {
    if (pingIntervalRef !== null) {
      clearInterval(pingIntervalRef);
      pingIntervalRef = null;
    }
  }

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

        // Отправляем ping для поддержания соединения.
        // Stored in the outer-scope ref so close()/onclose can clear it.
        clearPingInterval();
        pingIntervalRef = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          } else {
            // Socket is closing/closed — clear the interval to stop the leak.
            clearPingInterval();
          }
        }, 30000);
      };

      ws.onmessage = (ev) => {
        try {
          const obj = safeJsonParse(ev.data);
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
        // Clear the ping interval immediately — the socket is gone, pings
        // would either throw or silently no-op, but the interval itself
        // would keep firing forever without this.
        clearPingInterval();
        onDisconnect && onDisconnect();

        // DISPLAYWS-FE-004 (audit PR #3961): автоматическое
        // переподключение с ограниченным экспоненциальным backoff и
        // джиттером — без перманентного обрыва после 5 попыток.
        if (event.code !== 1000) {
          reconnectAttempts++;
          const backoff = Math.min(
            reconnectBaseDelayMs * Math.pow(2, reconnectAttempts - 1),
            maxReconnectDelayMs
          );
          const jitter = Math.floor(Math.random() * 500);
          logger.log(`🔄 Попытка переподключения ${reconnectAttempts} через ${backoff + jitter}ms`);

          reconnectTimeout = setTimeout(() => {
            connect();
          }, backoff + jitter);
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
      // audit/phase-4, BS-14: clear the ping interval BEFORE closing the
      // socket — otherwise the onclose handler runs AFTER our cleanup and
      // could schedule a reconnect that we won't be able to cancel.
      clearPingInterval();

      if (ws) {
        // Null the handlers before close so the synthetic onclose fired by
        // the browser doesn't trigger reconnect logic on a manual close.
        ws.onclose = null;
        ws.onerror = null;
        ws.onopen = null;
        ws.onmessage = null;
        ws.close(1000, 'Закрытие по запросу');
        ws = null;
      }
    } catch (error) {
      logger.warn('Ошибка закрытия WebSocket:', error);
    }
  };
}
