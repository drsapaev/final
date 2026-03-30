import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { notificationsService } from '../api/services';
import logger from '../utils/logger';

const NotificationCenterContext = createContext(null);

export const ROLE_NOTIFICATION_TYPES = {
  doctor: ['diagnostics_return', 'queue_changed', 'lab_critical_result'],
  registrar: ['new_appointment', 'queue_status_changed', 'registrar_system_alert'],
  lab: ['lab_new_study', 'lab_critical_finding', 'lab_result_sent_confirmation'],
  patient: ['appointment_reminder', 'appointment_rescheduled', 'payment_update', 'result_ready'],
  cardiologist: ['diagnostics_return', 'queue_changed', 'lab_critical_result'],
  dermatologist: ['diagnostics_return', 'queue_changed', 'lab_critical_result'],
  dentist: ['diagnostics_return', 'queue_changed', 'lab_critical_result'],
  admin: ['registrar_system_alert', 'system_alert', 'security_alert', 'billing_alert']
};

function normalizeNotificationType(type) {
  const normalized = String(type || 'system').toLowerCase();
  if (normalized === 'queue_update') {
    return 'queue_changed';
  }
  return normalized;
}

function normalizeNotification(input, source = 'api') {
  const createdAt = input.created_at || input.createdAt || new Date().toISOString();
  return {
    id: input.id || input.notification_id || input.event_id || `${source}-${Date.now()}-${Math.random()}`,
    type: normalizeNotificationType(input.type || input.event_type || input.notification_type),
    title: input.title || input.subject || 'Уведомление',
    message: input.message || input.body || '',
    createdAt,
    isRead: Boolean(input.is_read ?? input.isRead ?? false),
    role: input.role || input.target_role || input.recipient_role || null,
    raw: input
  };
}

function inferRoleFromType(type) {
  const normalizedType = String(type || '').toLowerCase();
  for (const [role, types] of Object.entries(ROLE_NOTIFICATION_TYPES)) {
    if (types.includes(normalizedType)) {
      return role;
    }
  }
  return null;
}

export function NotificationCenterProvider({ children }) {
  const [inbox, setInbox] = useState([]);

  const appendNotification = useCallback((event, source = 'ws') => {
    const normalized = normalizeNotification(event, source);
    const inferredRole = normalized.role || inferRoleFromType(normalized.type);
    const enriched = { ...normalized, role: inferredRole };

    setInbox((current) => {
      const existingIdx = current.findIndex((item) => String(item.id) === String(enriched.id));
      if (existingIdx >= 0) {
        const next = [...current];
        next[existingIdx] = {
          ...next[existingIdx],
          ...enriched,
          isRead: next[existingIdx].isRead || enriched.isRead
        };
        return next;
      }
      return [enriched, ...current].slice(0, 200);
    });

    return enriched;
  }, []);

  const loadNotifications = useCallback(async (params = {}) => {
    try {
      const payload = await notificationsService.getHistory(params);
      const list = Array.isArray(payload)
        ? payload
        : payload?.results || payload?.items || payload?.data || payload?.notifications || [];
      const normalizedList = list.map((item) => normalizeNotification(item, 'api'));
      setInbox((current) => {
        const merged = [...current, ...normalizedList];
        const unique = [];
        const seen = new Set();
        merged.forEach((item) => {
          const key = String(item.id);
          if (seen.has(key)) return;
          seen.add(key);
          unique.push(item);
        });
        return unique.slice(0, 200);
      });
      return normalizedList;
    } catch (error) {
      logger.error('[NotificationCenter] loadNotifications failed', error);
      throw error;
    }
  }, []);

  const markAsRead = useCallback(async (notificationId) => {
    setInbox((current) => current.map((item) => (
      String(item.id) === String(notificationId) ? { ...item, isRead: true } : item
    )));
    return notificationId;
  }, []);

  const markAllAsRead = useCallback(async (role = null) => {
    setInbox((current) => current.map((item) => {
      if (role && item.role && item.role !== role) {
        return item;
      }
      return { ...item, isRead: true };
    }));
  }, []);

  const getNotificationsByRole = useCallback((role) => {
    if (!role) return inbox;
    return inbox.filter((item) => !item.role || item.role === role);
  }, [inbox]);

  const getUnreadCount = useCallback((role = null) => {
    const list = role ? getNotificationsByRole(role) : inbox;
    return list.filter((item) => !item.isRead).length;
  }, [getNotificationsByRole, inbox]);

  const value = useMemo(() => ({
    inbox,
    appendNotification,
    loadNotifications,
    markAsRead,
    markAllAsRead,
    getNotificationsByRole,
    getUnreadCount
  }), [inbox, appendNotification, loadNotifications, markAsRead, markAllAsRead, getNotificationsByRole, getUnreadCount]);

  return (
    <NotificationCenterContext.Provider value={value}>
      {children}
    </NotificationCenterContext.Provider>
  );
}

NotificationCenterProvider.propTypes = {
  children: PropTypes.node.isRequired
};

export function useNotificationCenter() {
  const ctx = useContext(NotificationCenterContext);
  if (!ctx) {
    throw new Error('useNotificationCenter must be used within NotificationCenterProvider');
  }
  return ctx;
}
