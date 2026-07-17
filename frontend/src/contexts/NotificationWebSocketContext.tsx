import { createContext, useCallback, useContext, useEffect, useRef, type ReactNode, type MutableRefObject } from 'react';
import PropTypes from 'prop-types';
import { useLocation } from 'react-router-dom';
import { buildWsUrl } from '../api/runtime';
import notify from '../services/notify';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
import { useNotificationCenter } from './NotificationCenterContext';
import { clearNotificationQueryCache } from '../api/services';
import { isPublicRoutePath } from '../routing/routeSelectors';

// Inbound WS payloads are dynamic JSON — they share the wire shape of
// { type, title, message, ... } but the backend may extend fields. We
// model the canonical surface and stash the raw payload for debug.
interface WsPayload {
  notification?: WsPayload;
  payload?: WsPayload;
  data?: WsPayload;
  type?: unknown;
  event_type?: unknown;
  notification_type?: unknown;
  title?: unknown;
  subject?: unknown;
  message?: unknown;
  content?: unknown;
  user_id?: unknown;
  role?: unknown;
  unread_count?: unknown;
  unreadCount?: unknown;
  by_role?: Record<string, unknown> | null;
  by_channel?: Record<string, unknown> | null;
  by_severity?: Record<string, unknown> | null;
  items?: unknown[];
  [key: string]: unknown;
}

interface NormalizedNotification {
  type: string;
  title: string;
  message: string;
  raw: WsPayload;
  nested: WsPayload;
}

interface UnreadSnapshot {
  total: number;
  by_role?: Record<string, unknown> | null;
  by_channel?: Record<string, unknown> | null;
  by_severity?: Record<string, unknown> | null;
}

interface AppendMeta {
  replace?: boolean;
}

interface ReplaceMeta {
  source?: string;
  unreadSnapshot?: UnreadSnapshot;
  lastSyncAt?: string;
}

// NotificationCenterContext is still @ts-nocheck. Cast its return type to
// a structural interface here so we get strong typing on the three methods
// we actually depend on. When NotificationCenterContext is migrated, the
// cast can be removed.
interface NotificationCenterHandle {
  appendNotification: (event: WsPayload | Record<string, unknown>, source?: string) => unknown;
  replaceNotifications: (items: unknown[], meta?: ReplaceMeta) => void;
  updateUnreadSnapshot: (snapshot: UnreadSnapshot, options?: AppendMeta) => void;
}

type ToastType = 'error' | 'warning' | 'success' | 'info';

interface NotificationWebSocketContextValue {
  ws: WebSocket | null;
}

const NotificationWebSocketContext = createContext<NotificationWebSocketContextValue | null>(null);

const TYPE_ALIASES: Record<string, string> = {
  queue_changed: 'queue_update',
  diagnostics_return: 'diagnostics_return_needed'
};

function normalizePayload(payload: WsPayload = {}): NormalizedNotification {
  const nested = (payload.notification || payload.payload || payload.data || payload) as WsPayload;
  const rawType =
    nested.type ||
    nested.event_type ||
    nested.notification_type ||
    payload.type ||
    payload.event_type ||
    payload.notification_type ||
    'notification';
  const normalizedRawType = String(rawType).toLowerCase();
  const type = TYPE_ALIASES[normalizedRawType] || normalizedRawType;

  const title =
    (nested.title as string) ||
    (nested.subject as string) ||
    (type === 'queue_update' ? 'Обновление очереди' : 'Уведомление');
  const message =
    (nested.message as string) ||
    (nested.content as string) ||
    (payload.message as string) ||
    (payload.content as string) ||
    '';

  return { type, title, message, raw: payload, nested };
}

interface NotificationWebSocketProviderProps {
  children: ReactNode;
}

export function NotificationWebSocketProvider({ children }: NotificationWebSocketProviderProps) {
  const ws = useRef<WebSocket | null>(null);
  const handleMessageRef = useRef<(data: WsPayload) => void>(() => {});
  const connectRef = useRef<(() => (() => void) | undefined) | null>(null);
  const connectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const disconnectRef = useRef<(() => void) | null>(null);
  const closeOnOpenRef = useRef<WebSocket | null>(null);
  const closeOnOpenReasonRef = useRef<string>('');
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnect = useRef<boolean>(true);
  const location = useLocation();
  const { appendNotification, replaceNotifications, updateUnreadSnapshot } =
    useNotificationCenter() as NotificationCenterHandle;

  const closeSocketSafely = useCallback((socket: WebSocket | null, reason: string) => {
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
      connectRef.current?.();
    }, 3000);
  }, []);

  const applyUnreadSnapshot = useCallback((data: WsPayload) => {
    if (
      typeof data?.unread_count === 'number' ||
      typeof data?.unreadCount === 'number' ||
      data?.by_role ||
      data?.by_channel ||
      data?.by_severity
    ) {
      const snapshot: UnreadSnapshot = {
        total: Number(data?.unread_count ?? data?.unreadCount ?? 0),
        by_role: data?.by_role ?? null,
        by_channel: data?.by_channel ?? null,
        by_severity: data?.by_severity ?? null
      };
      updateUnreadSnapshot(snapshot, { replace: false });
    }
  }, [updateUnreadSnapshot]);

  useEffect(() => {
    handleMessageRef.current = (data: WsPayload) => {
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
        ) as { message?: string; title?: string; type?: string };

        const toastMessage = notification.message
          ? `${notification.title}: ${notification.message}`
          : (notification.title ?? '');
        const toastType: ToastType = (notification.type ?? '').includes('error')
          ? 'error'
          : (notification.type ?? '').includes('warning') || (notification.type ?? '').includes('alert')
            ? 'warning'
            : (notification.type ?? '').includes('success')
              ? 'success'
              : 'info';

        notify[toastType](toastMessage);

        if (
          typeof Notification !== 'undefined' &&
          document.hidden &&
          Notification.permission === 'granted'
        ) {
          new Notification(notification.title ?? '', { body: notification.message ?? '' });
        }
      }
    };
  }, [appendNotification, applyUnreadSnapshot, replaceNotifications]);

  const connect = useCallback((): (() => void) | undefined => {
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

    socket.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as WsPayload;
        handleMessageRef.current(data);
      } catch (error) {
        logger.error('[NotificationWS] failed to parse message', error);
      }
    };

    socket.onclose = (event: CloseEvent) => {
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

  (connectRef as MutableRefObject<typeof connect | null>).current = connect;

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

export function useNotificationWebSocket(): NotificationWebSocketContextValue | null {
  return useContext(NotificationWebSocketContext);
}
