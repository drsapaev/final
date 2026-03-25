import { createContext, useContext, useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import { buildWsUrl } from '../api/runtime';
import { useToast } from '../components/common/Toast';
import { useNotifications } from '../hooks/useNotifications';
import { pushNotifications } from '../services/pushNotifications';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

const NotificationWebSocketContext = createContext(null);

const WS_DOMAIN_MAP = {
  queue_update: 'queue',
  lab_result_ready: 'lab',
  payment_confirmed: 'payment',
  appointment_reminder: 'appointment'
};

const ROLE_DOMAIN_RULES = {
  doctor: new Set(['queue', 'lab', 'system']),
  cardiologist: new Set(['queue', 'lab', 'system']),
  dermatologist: new Set(['queue', 'lab', 'system']),
  dentist: new Set(['queue', 'lab', 'system']),
  registrar: new Set(['appointment', 'queue', 'payment', 'system']),
  cashier: new Set(['payment', 'appointment', 'system']),
  lab: new Set(['lab', 'queue', 'system']),
  patient: new Set(['appointment', 'lab', 'payment', 'system']),
  admin: new Set(['queue', 'lab', 'payment', 'appointment', 'system'])
};

function resolveRole() {
  const roleRaw = tokenManager.getRole?.() || localStorage.getItem('userRole') || tokenManager.getUserData?.()?.role || '';
  const role = String(roleRaw).toLowerCase();

  if (role.includes('cardio')) return 'cardiologist';
  if (role.includes('derma')) return 'dermatologist';
  if (role.includes('dent') || role.includes('stomat')) return 'dentist';
  if (role.includes('cash')) return 'cashier';
  if (role.includes('registrar')) return 'registrar';
  if (role.includes('lab')) return 'lab';
  if (role.includes('patient')) return 'patient';
  if (role.includes('admin')) return 'admin';
  if (role.includes('doctor')) return 'doctor';

  return role;
}

function mapNotificationPayload(data) {
  const domain = data.domain || data.meta?.domain || WS_DOMAIN_MAP[data.type] || 'system';
  return {
    ...data,
    domain,
    notification_type: data.notification_type || data.level || data.severity || 'info',
    payload: {
      ...(data.payload || {}),
      ...(data.meta || {})
    }
  };
}

function isRoleRelevant(role, domain) {
  if (!role || !ROLE_DOMAIN_RULES[role]) {
    return true;
  }
  return ROLE_DOMAIN_RULES[role].has(domain);
}

export function NotificationWebSocketProvider({ children }) {
  const ws = useRef(null);
  const { addToast } = useToast();
  const { addNotification } = useNotifications();
  const reconnectTimeout = useRef(null);

  const handleMessage = useCallback((data) => {
    if (data.type !== 'notification' && data.type !== 'queue_update') {
      return;
    }

    const normalizedPayload = mapNotificationPayload(data);
    const role = resolveRole();

    if (!isRoleRelevant(role, normalizedPayload.domain)) {
      return;
    }

    const notification = addNotification(normalizedPayload);

    addToast({
      title: notification.title,
      message: notification.message,
      type: notification.type || 'info',
      duration: 5000
    });

    if (document.hidden) {
      pushNotifications.showOperationalNotification(notification);
    }
  }, [addNotification, addToast]);

  const connect = useCallback(() => {
    let activeSocket = null;
    const token = tokenManager.getAccessToken();
    if (!token || !tokenManager.isTokenValid()) {
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
    </NotificationWebSocketContext.Provider>
  );
}

NotificationWebSocketProvider.propTypes = {
  children: PropTypes.node.isRequired
};

export function useNotificationWebSocket() {
  return useContext(NotificationWebSocketContext);
}
