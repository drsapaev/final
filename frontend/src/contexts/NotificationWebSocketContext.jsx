
import { createContext, useContext, useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useToast } from '../components/common/Toast';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

const NotificationWebSocketContext = createContext(null);

export function NotificationWebSocketProvider({ children }) {
  const ws = useRef(null);
  const { addToast } = useToast();
  const reconnectTimeout = useRef(null);

  const handleMessage = useCallback((data) => {
    if (data.type === 'notification') {
      const { title, message } = data;
      // Use Toast to show notification
      // meta.type can be 'error', 'success', etc. if needed
      addToast({
        title: title,
        message: message,
        type: 'info', // Default to info, or map from meta.type
        duration: 5000
        // Optional: onClick logic using meta (e.g. navigate to queued item)
      });

      // If browsers support Notification API and permission granted, we could also show system notification
      if (document.hidden && Notification.permission === 'granted') {
        new Notification(title, { body: message });
      }
    } else if (data.type === 'queue_update') {
      // Specific handling for queue updates if needed
      addToast({
        title: 'Обновление очереди',
        message: 'Ваш статус обновлен',
        type: 'info'
      });
    }
  }, [addToast]);

  const connect = useCallback(() => {
    let activeSocket = null;
    const token = tokenManager.getAccessToken();
    if (!token || !tokenManager.isTokenValid()) {
      // Retry later if no token (e.g. not logged in)
      reconnectTimeout.current = setTimeout(connect, 5000);
      return () => {};
    }

    // Determine WebSocket Protocol (ws/wss) based on current page
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use the backend host or default to same-origin with standard port
    // Simplification: assume backend on port 8000 or proxy. 
    // Ideally use environment variable.
    // Given the rest of the app:
    const host = window.location.hostname;
    // Standard backend port in dev is 8000. In prod, likely same port.
    // If we have API_URL environment variable, we should parse it.
    // For now, let's try a safe bet or a configurable url.
    // Assuming backend is at localhost:8000 for dev environments.

    // Better strategy: Use a known base URL config if available
    let wsUrl = `${protocol}//${host}:8000/api/v1/notification-websocket/ws/notifications/connect?token=${token}`;

    // BUT wait, in existing code, endpoints are often referenced via imports.
    // The endpoint I created is in `app/api/v1/endpoints/notification_websocket.py`
    // And registered as `notification_websocket.router` with tags=["notification-websocket"].
    // It does NOT have a prefix in `api.py`.
    // Wait, let's check api.py again.

    /*
    api_router.include_router(
        notification_websocket.router, tags=["notification-websocket"]
    )
    */

    // And the router implementation:
    // @router.websocket("/ws/notifications/connect")

    // So the full path is `/api/v1/ws/notifications/connect`.

    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
    // Convert http(s) to ws(s)
    const wsBase = apiBase.replace(/^http/, 'ws');
    wsUrl = `${wsBase}/ws/notifications/connect?token=${token}`;

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
