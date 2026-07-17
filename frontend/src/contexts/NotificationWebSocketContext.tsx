// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { createContext, useCallback, useContext, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import { useLocation } from 'react-router-dom';
import { buildWsUrl } from '../api/runtime';
import notify from '../services/notify';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
import { useNotificationCenter } from './NotificationCenterContext';
import { clearNotificationQueryCache } from '../api/services';
import { isPublicRoutePath } from '../routing/routeSelectors';

const NotificationWebSocketContext = createContext<unknown>(null);

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
  const normalizedRawType = String(rawType).toLowerCase();
  const typeAliases = {
    queue_changed: 'queue_update',
    diagnostics_return: 'diagnostics_return_needed',
  };
  const type = typeAliases[normalizedRawType] || normalizedRawType;

  const title =
    nested.title ||
    nested.subject ||
    (type === 'queue_update' ? 'Обновление очереди' : 'Уведомление');
  const message = nested.message || nested.content || payload.message || payload.content || '';

  return { type, title, message, raw: payload, nested };
}

export function NotificationWebSocketProvider({ children }) {
  const ws = useRef<unknown>(null);
  const handleMessageRef = useRef(() => {});
  const connectRef = useRef<unknown>(null);
  const connectTimerRef = useRef<unknown>(null);
  const disconnectRef = useRef<unknown>(null);
  const closeOnOpenRef = useRef<unknown>(null);
  const closeOnOpenReasonRef = useRef('');
  const reconnectTimeout = useRef<unknown>(null);
  const shouldReconnect = useRef(true);
  const location = useLocation();
  const { appendNotification, replaceNotifications, updateUnreadSnapshot } = useNotificationCenter();

  const closeSocketSafely = useCallback((socket, reason) => {
    if (!socket) {
      return;
    }

    if (socket.readyState === WebSocket.OPEN) {
      try {
        socket.close(1000, reason);
      } catch (error) {
        logger.warn('[NotificationWS] failed to close socket', error);
      }
      return;
    }

    if (socket.readyState === WebSocket.CONNECTING) {
      closeOnOpenRef.current = socket;
      closeOnOpenReasonRef.current = reason;
    }
  }, []);

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

  useEffect(() => {
    handleMessageRef.current = (data) => {
      const normalized = normalizePayload(data);

      const invalidateNotificationCache = () => {
        clearNotificationQueryCache();
      };

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
        invalidateNotificationCache();
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
        invalidateNotificationCache();
        applyUnreadSnapshot(data);
        return;
      }

      if (
        normalized.type === 'notification' ||
        normalized.type === 'queue_update' ||
        normalized.type === 'diagnostics_return_needed' ||
        normalized.type === 'system_alert'
      ) {
        invalidateNotificationCache();
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
    };
  }, [appendNotification, applyUnreadSnapshot, replaceNotifications]);

  const connect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }

    if (ws.current && (
      ws.current.readyState === WebSocket.OPEN ||
      ws.current.readyState === WebSocket.CONNECTING
    )) {
      return () => {};
    }

    const token = tokenManager.getAccessToken();
    if (!token || !tokenManager.isTokenValid()) {
      scheduleReconnect();
      return () => {};
    }

    const wsUrl = `${buildWsUrl('/api/v1/ws/notifications/connect')}`;
    const socket = new WebSocket(wsUrl, [`bearer.${token}`]);  // P1-6: token via subprotocol;
    ws.current = socket;

    socket.onopen = () => {
      if (closeOnOpenRef.current === socket) {
        closeOnOpenRef.current = null;
        const reason = closeOnOpenReasonRef.current || 'Public route';
        closeOnOpenReasonRef.current = '';
        try {
          socket.close(1000, reason);
        } catch (error) {
          logger.warn('[NotificationWS] failed to close socket after connect', error);
        }
        return;
      }

      logger.info('[NotificationWS] connected');
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessageRef.current(data);
      } catch (error) {
        logger.error('[NotificationWS] failed to parse message', error);
      }
    };

    socket.onclose = (event) => {
      if (ws.current === socket) {
        ws.current = null;
      }
      if (closeOnOpenRef.current === socket) {
        closeOnOpenRef.current = null;
        closeOnOpenReasonRef.current = '';
      }
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
      closeSocketSafely(socket, 'Unmount');
    };
  }, [closeSocketSafely, scheduleReconnect]);

  connectRef.current = connect;

  useEffect(() => {
    const isPublicRoute = isPublicRoutePath(location.pathname);

    shouldReconnect.current = !isPublicRoute;

    if (connectTimerRef.current) {
      clearTimeout(connectTimerRef.current);
      connectTimerRef.current = null;
    }

    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }

    if (isPublicRoute) {
      if (disconnectRef.current) {
        disconnectRef.current();
        disconnectRef.current = null;
      }
      const socket = ws.current;
      closeSocketSafely(socket, 'Public route');
      return () => {};
    }

    connectTimerRef.current = setTimeout(() => {
      disconnectRef.current = connectRef.current?.() || null;
    }, 0);

    return () => {
      if (connectTimerRef.current) {
        clearTimeout(connectTimerRef.current);
        connectTimerRef.current = null;
      }
      if (disconnectRef.current) {
        disconnectRef.current();
        disconnectRef.current = null;
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      closeSocketSafely(ws.current, 'Unmount');
    };
  }, [closeSocketSafely, connect, location.pathname]);

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
