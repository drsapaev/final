import { createContext, useContext, useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import { buildWsUrl } from '../api/runtime';
import notify from '../services/notify';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
import { useNotificationCenter } from './NotificationCenterContext';

const NotificationWebSocketContext = createContext(null);

function normalizePayload(payload = {}) {
  const nested = payload.notification || payload;
  const rawType =
    nested.type ||
    nested.event_type ||
    nested.notification_type ||
    payload.type ||
    payload.event_type ||
    payload.notification_type ||
    'notification';
  const type = String(rawType).toLowerCase() === 'queue_update' ? 'queue_changed' : String(rawType).toLowerCase();

  const title =
    nested.title ||
    nested.subject ||
    (type === 'queue_changed' ? 'Обновление очереди' : 'Уведомление');
  const message = nested.message || nested.content || payload.message || payload.content || '';

  return { type, title, message, raw: payload };
}

export function NotificationWebSocketProvider({ children }) {
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);
  const { appendNotification } = useNotificationCenter();

  const handleMessage = useCallback((data) => {
    const normalized = normalizePayload(data);
    if (normalized.type === 'connection_established') {
      logger.info('[FIX:WS] Notification WebSocket handshake confirmed', {
        userId: data.user_id
      });
      return;
    }

    if (normalized.type === 'notification' || normalized.type === 'queue_changed' || normalized.type === 'system_alert') {
      const notification = appendNotification(
        {
          ...data,
          type: normalized.type,
          title: normalized.title,
          message: normalized.message
        },
        'ws'
      );

      const toastMessage = notification.message
        ? `${notification.title}: ${notification.message}`
        : notification.title;
      const toastType = notification.type.includes('error')
        ? 'error'
        : notification.type.includes('warning') || notification.type.includes('alert')
          ? 'warning'
          : notification.type.includes('success')
            ? 'success'
            : 'info';

      notify[toastType](toastMessage);

      if (typeof Notification !== 'undefined' && document.hidden && Notification.permission === 'granted') {
        new Notification(notification.title, { body: notification.message });
      }
    }
  }, [appendNotification]);

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
