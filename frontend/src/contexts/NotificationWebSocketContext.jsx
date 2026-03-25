
import { createContext, useContext, useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import { buildWsUrl } from '../api/runtime';
import { useToast } from '../components/common/Toast';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

const NotificationWebSocketContext = createContext(null);

export function NotificationWebSocketProvider({ children }) {
  const ws = useRef(null);
  const { addToast } = useToast();
  const reconnectTimeout = useRef(null);

  const normalizeNotification = useCallback((payload = {}) => {
    const data = payload.notification || payload;
    const title = data.title || data.subject || 'Уведомление';
    const message = data.message || data.content || payload.message || '';
    const rawType = (data.level || data.severity || data.type || 'info').toLowerCase();
    const type = ['success', 'error', 'warning', 'info'].includes(rawType)
      ? rawType
      : 'info';
    return { title, message, type };
  }, []);

  const handleMessage = useCallback((data) => {
    if (data.type === 'notification' || data.type === 'queue_update' || data.type === 'system_alert') {
      const normalized = normalizeNotification(data);
      // Use Toast to show notification
      // meta.type can be 'error', 'success', etc. if needed
      addToast({
        title: normalized.title,
        message: normalized.message,
        type: normalized.type, // Default to info, or map from meta.type
        duration: 5000
        // Optional: onClick logic using meta (e.g. navigate to queued item)
      });

      // If browsers support Notification API and permission granted, we could also show system notification
      if (document.hidden && Notification.permission === 'granted') {
        new Notification(normalized.title, { body: normalized.message });
      }
    } else if (data.type === 'connection_established') {
      logger.info('[FIX:WS] Notification WebSocket handshake confirmed', {
        userId: data.user_id
      });
    }
  }, [addToast, normalizeNotification]);

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
