
import { createContext, useContext, useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import { buildWsUrl } from '../api/runtime';
import { notify, normalizeNotificationPayload } from '../services/notifications/uiNotifications';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

const NotificationWebSocketContext = createContext(null);

export function NotificationWebSocketProvider({ children }) {
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);

  const handleMessage = useCallback((data) => {
    if (data.type === 'notification' || data.type === 'queue_update') {
      const payload = normalizeNotificationPayload(data, {
        title: data.type === 'queue_update' ? 'Обновление очереди' : 'Уведомление',
        message: data.type === 'queue_update' ? 'Ваш статус обновлен' : 'Новое событие',
        type: data.meta?.type || 'info',
        source: data.source || 'websocket',
        entity_type: data.entity_type || data.meta?.entity_type || null,
        entity_id: data.entity_id || data.meta?.entity_id || null,
        action_url: data.action_url || data.meta?.action_url || null,
      });

      notify.system(payload);

      if (document.hidden && Notification.permission === 'granted') {
        new Notification(payload.title || 'Уведомление', { body: payload.message });
      }
    }
  }, []);

  const connect = useCallback(() => {
    let activeSocket = null;
    const token = tokenManager.getAccessToken();
    if (!token || !tokenManager.isTokenValid()) {
      // Retry later if no token (e.g. not logged in)
      reconnectTimeout.current = setTimeout(connect, 5000);
      return () => {};
    }

    const wsUrl = `${buildWsUrl('/api/v1/ws/notifications/connect')}?token=${token}`;

    const socket = new WebSocket(wsUrl);
    activeSocket = socket;

    socket.onopen = () => {
      logger.info('[FIX:WS] Notification WebSocket connected');
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        logger.error('Error parsing WS message:', e);
      }
    };

    socket.onclose = (event) => {
      logger.info('[FIX:WS] Notification WebSocket closed. Reconnecting...', {
        code: event.code
      });
      ws.current = null;
      reconnectTimeout.current = setTimeout(connect, 3000);
    };

    socket.onerror = () => {
      logger.warn('[FIX:WS] Notification WebSocket handshake failed; waiting for retry');
      socket.close();
    };

    ws.current = socket;
    return () => {
      if (activeSocket?.readyState === WebSocket.OPEN) {
        activeSocket.close(1000, 'Unmount');
      } else if (activeSocket?.readyState === WebSocket.CONNECTING) {
        activeSocket.onopen = () => activeSocket.close(1000, 'Unmount before open');
        activeSocket.onclose = null;
        activeSocket.onerror = null;
        activeSocket.onmessage = null;
      }
    };
  }, [handleMessage]);

  useEffect(() => {
    const disconnect = connect();
    return () => {
      disconnect?.();
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [connect]);

  return (
    <NotificationWebSocketContext.Provider value={{ ws: ws.current }}>
            {children}
        </NotificationWebSocketContext.Provider>);

}

NotificationWebSocketProvider.propTypes = {
  children: PropTypes.node.isRequired
};

export function useNotificationWebSocket() {
  return useContext(NotificationWebSocketContext);
}
