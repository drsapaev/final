/**
 * useQueueWebSocket — React hook для подписки на /ws/queue.
 *
 * UX Audit Stage 3 (Queue issue 7.1):
 * Заменяет 30-секундный polling в ModernQueueManager на мгновенные
 * обновления через WebSocket. Backend уже имеет /ws/queue endpoint
 * (backend/app/ws/queue_ws.py) и broadcast_queue_update() helper,
 * который вызывается из queue endpoints при мутациях.
 *
 * Архитектура:
 *   1. Hook подключается к /ws/queue?department=specialist_{id}&date={date}&token={token}
 *   2. При получении сообщения {type: 'queue_update', ...} вызывает onUpdate callback
 *   3. Callback перезагружает snapshot очереди (loadQueueSnapshot)
 *   4. Polling остаётся как fallback (на случай обрыва WS)
 *
 * Reconnection:
 *   - При обрыве WS hook переподключается через 3с, потом 6с, потом 12с (exponential backoff)
 *   - Максимум 5 попыток, потом переключается на polling-only режим
 *
 * Usage:
 *   import { useQueueWebSocket } from '../../hooks/useQueueWebSocket';
 *
 *   const { isConnected, connectionState } = useQueueWebSocket({
 *     specialistId: effectiveDoctor,
 *     date: effectiveDate,
 *     enabled: Boolean(effectiveDoctor && effectiveDate),
 *     onUpdate: () => loadQueueSnapshot(),
 *   });
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { buildWsUrl } from '../api/runtime';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

const RECONNECT_DELAYS = [3000, 6000, 12000, 24000, 30000]; // exponential backoff
const MAX_RECONNECT_ATTEMPTS = 5;

/**
 * @param {object} options
 * @param {string|number} options.specialistId - ID специалиста (для room)
 * @param {string} options.date - Дата в YYYY-MM-DD формате (для room)
 * @param {boolean} options.enabled - Включена ли подписка (false = отключена)
 * @param {() => void} options.onUpdate - Callback при получении обновления
 * @returns {{isConnected: boolean, connectionState: 'disconnected'|'connecting'|'connected'|reconnecting'}}
 */
export function useQueueWebSocket({ specialistId, date, enabled = true, onUpdate }) {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState('disconnected');
  const wsRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const onUpdateRef = useRef(onUpdate);

  // Keep onUpdate ref current without re-triggering effect
  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onclose = null; // prevent reconnect on manual close
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!specialistId || !date) {
      return;
    }

    const token = tokenManager.getAccessToken();
    if (!token) {
      logger.warn('[useQueueWebSocket] No auth token, skipping connection');
      return;
    }

    const department = `specialist_${specialistId}`;
    const wsUrl = `${buildWsUrl('/ws/queue')}?department=${encodeURIComponent(department)}&date=${encodeURIComponent(date)}&token=${encodeURIComponent(token)}`;

    setConnectionState(reconnectAttemptRef.current > 0 ? 'reconnecting' : 'connecting');

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        logger.info('[useQueueWebSocket] Connected', { department, date });
        setIsConnected(true);
        setConnectionState('connected');
        reconnectAttemptRef.current = 0; // reset backoff on successful connect
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Ignore heartbeat pings
          if (data.type === 'ping' || data.type === 'pong') {
            return;
          }

          // Handle queue update events
          if (data.type === 'queue_update' || data.type === 'patient_called') {
            logger.log('[useQueueWebSocket] Received update', data);
            if (onUpdateRef.current) {
              onUpdateRef.current();
            }
          }

          // Handle dev/connected acknowledgements
          if (data.type === 'dev.accepted' || data.type === 'connected') {
            logger.log('[useQueueWebSocket] Server acknowledged connection', data);
          }

          // Handle errors from server
          if (data.type === 'error') {
            logger.warn('[useQueueWebSocket] Server error', data);
          }
        } catch (parseError) {
          logger.warn('[useQueueWebSocket] Failed to parse message', parseError);
        }
      };

      ws.onerror = (error) => {
        logger.warn('[useQueueWebSocket] WebSocket error', error);
        // onclose will handle reconnection
      };

      ws.onclose = (event) => {
        logger.info('[useQueueWebSocket] Disconnected', { code: event.code, reason: event.reason });
        setIsConnected(false);
        wsRef.current = null;

        // Don't reconnect if manually closed (code 1000) or if disabled
        if (event.code === 1000) {
          setConnectionState('disconnected');
          return;
        }

        // Attempt reconnection with exponential backoff
        if (reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = RECONNECT_DELAYS[reconnectAttemptRef.current] || 30000;
          reconnectAttemptRef.current += 1;
          setConnectionState('reconnecting');
          logger.info(
            `[useQueueWebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptRef.current}/${MAX_RECONNECT_ATTEMPTS})`
          );
          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else {
          logger.warn('[useQueueWebSocket] Max reconnection attempts reached, switching to polling-only');
          setConnectionState('disconnected');
        }
      };
    } catch (error) {
      logger.error('[useQueueWebSocket] Failed to create WebSocket', error);
      setConnectionState('disconnected');
    }
  }, [specialistId, date]);

  useEffect(() => {
    if (!enabled) {
      cleanup();
      setConnectionState('disconnected');
      return undefined;
    }

    connect();

    return () => {
      cleanup();
    };
  }, [enabled, connect, cleanup]);

  return { isConnected, connectionState };
}

export default useQueueWebSocket;
