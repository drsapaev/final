import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import PropTypes from 'prop-types';

const NotificationsContext = createContext(null);

const MAX_NOTIFICATIONS = 200;

function normalizeDate(value) {
  if (!value) {
    return new Date().toISOString();
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString();
}

function mapDomain(source = {}) {
  return (
    source.domain
    || source.meta?.domain
    || source.payload?.domain
    || source.context?.domain
    || (source.type === 'queue_update' ? 'queue' : 'system')
  );
}

function mapNotificationType(source = {}) {
  return source.notification_type || source.level || source.severity || source.meta?.type || 'info';
}

export function normalizeNotificationEntity(raw = {}) {
  const fallbackId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  return {
    id: raw.id || raw.notification_id || raw.uuid || fallbackId,
    title: raw.title || raw.subject || 'Уведомление',
    message: raw.message || raw.body || raw.text || '',
    type: mapNotificationType(raw),
    created_at: normalizeDate(raw.created_at || raw.timestamp || raw.date),
    is_read: Boolean(raw.is_read || raw.read_at),
    domain: mapDomain(raw),
    action_url: raw.action_url || raw.link || raw.meta?.action_url || null,
    payload: raw.payload || raw.meta || {}
  };
}

export function NotificationsProvider({ children }) {
  const [notifications, setNotifications] = useState([]);

  const addNotification = useCallback((rawNotification) => {
    const normalized = normalizeNotificationEntity(rawNotification);
    setNotifications((prev) => [normalized, ...prev].slice(0, MAX_NOTIFICATIONS));
    return normalized;
  }, []);

  const markAsRead = useCallback((id) => {
    setNotifications((prev) => prev.map((item) => (item.id === id ? { ...item, is_read: true } : item)));
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((item) => ({ ...item, is_read: true })));
  }, []);

  const removeNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const unreadCount = useMemo(() => notifications.filter((item) => !item.is_read).length, [notifications]);

  const value = useMemo(() => ({
    notifications,
    unreadCount,
    addNotification,
    markAsRead,
    markAllAsRead,
    removeNotification
  }), [addNotification, markAllAsRead, markAsRead, notifications, removeNotification, unreadCount]);

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}

NotificationsProvider.propTypes = {
  children: PropTypes.node.isRequired
};

export function useNotifications() {
  const context = useContext(NotificationsContext);
  if (!context) {
    throw new Error('useNotifications must be used within NotificationsProvider');
  }
  return context;
}
