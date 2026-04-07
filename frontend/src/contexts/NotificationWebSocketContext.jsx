import { createContext, useCallback, useContext, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import { buildWsUrl } from '../api/runtime';
import notify from '../services/notify';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
import { useNotificationCenter } from './NotificationCenterContext';

const NotificationWebSocketContext = createContext(null);

function normalizePayload(payload = {}) {
  const nested = payload.notification || payload.payload || payload.data || payload;
  const rawType =
    nested.type ||
    nested.event_type ||
    nested.notification_type ||
    payload.type ||
    payload.event_type ||
    payload.notification_type ||
    'notification';
  const type = String(rawType).toLowerCase() === 'queue_update'
    ? 'queue_changed'
    : String(rawType).toLowerCase();

  const title =
    nested.title ||
    nested.subject ||
    (type === 'queue_changed' ? 'Обновление очереди' : 'Уведомление');
  const message = nested.message || nested.content || payload.message || payload.content || '';

  return { type, title, message, raw: payload, nested };
}

export function NotificationWebSocketProvider({ children }) {
  const ws = useRef(null);
  const connectRef = useRef(null);
  const reconnectTimeout = useRef(null);
  const shouldReconnect = useRef(true);
  const { appendNotification, replaceNotifications, updateUnreadSnapshot } = useNotificationCenter();

  const scheduleReconnect = useCallback(() => {
    if (!shouldReconnect.current) {
      return;
    }

    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
    }

    reconnectTimeout.current = setTimeout(() => {
      void connectRef.current?.();
    }, 3000);
  }, []);

  const applyUnreadSnapshot = useCallback((data) => {
    if (
      typeof data?.unread_count === 'number' ||
      typeof data?.unreadCount === 'number' ||
      data?.by_role ||
      data?.by_channel ||
      data?.by_severity
    ) {
      updateUnreadSnapshot(
        {
          total: Number(data?.unread_count ?? data?.unreadCount ?? 0),
          by_role: data?.by_role,
          by_channel: data?.by_channel,
          by_severity: data?.by_severity
        },
        { replace: false }
      );
    }
  }, [updateUnreadSnapshot]);

  const handleMessage = useCallback(
    (data) => {
      const normalized = normalizePayload(data);

      if (normalized.type === 'connection_established') {
        logger.info('[NotificationWS] handshake confirmed', {
          userId: data.user_id,
          role: data.role,
          unreadCount: data.unread_count
        });
        applyUnreadSnapshot(data);
        return;
      }

      if (normalized.type === 'notification_sync_response') {
        const items = Array.isArray(data.items) ? data.items : [];
        replaceNotifications(items, {
          source: 'ws',
          unreadSnapshot: {
            total: Number(data.unread_count ?? data.unreadCount ?? 0),
            by_role: data.by_role || {},
            by_channel: data.by_channel || {},
            by_severity: data.by_severity || {}
          },
          lastSyncAt: new Date().toISOString()
        });
        return;
      }

      if (
        normalized.type === 'notification_seen_ack' ||
        normalized.type === 'notification_read_ack' ||
        normalized.type === 'notification_archive_ack' ||
        normalized.type === 'notification_mark_all_read_ack'
      ) {
        applyUnreadSnapshot(data);
        return;
      }

      if (
        normalized.type === 'notification' ||
        normalized.type === 'queue_changed' ||
        normalized.type === 'system_alert'
      ) {
        const notification = appendNotification(
          {
            ...data,
            ...normalized.nested,
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

        if (
          typeof Notification !== 'undefined' &&
          document.hidden &&
          Notification.permission === 'granted'
        ) {
          new Notification(notification.title, { body: notification.message });
        }
      }
    },
    [appendNotification, applyUnreadSnapshot, replaceNotifications]
  );

  const connect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }

    const token = tokenManager.getAccessToken();
    if (!token || !tokenManager.isTokenValid()) {
      scheduleReconnect();
      return () => {};
    }

    const wsUrl = `${buildWsUrl('/api/v1/ws/notifications/connect')}?token=${token}`;
    const socket = new WebSocket(wsUrl);
    ws.current = socket;

    socket.onopen = () => {
      logger.info('[NotificationWS] connected');
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (error) {
        logger.error('[NotificationWS] failed to parse message', error);
      }
    };

    socket.onclose = (event) => {
      ws.current = null;
      logger.info('[NotificationWS] closed', { code: event.code, reason: event.reason });
      if (shouldReconnect.current) {
        scheduleReconnect();
      }
    };

    socket.onerror = () => {
      logger.warn('[NotificationWS] socket error, reconnecting');
      try {
        socket.close();
      } catch (error) {
        logger.warn('[NotificationWS] failed to close errored socket', error);
      }
    };

    return () => {
      shouldReconnect.current = false;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close(1000, 'Unmount');
      }
    };
  }, [handleMessage, scheduleReconnect]);

  connectRef.current = connect;

  useEffect(() => {
    shouldReconnect.current = true;
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
    </NotificationWebSocketContext.Provider>
  );
}

NotificationWebSocketProvider.propTypes = {
  children: PropTypes.node.isRequired
};

export function useNotificationWebSocket() {
  return useContext(NotificationWebSocketContext);
}
