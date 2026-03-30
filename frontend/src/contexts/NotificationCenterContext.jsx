import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { notificationsService } from '../api/services';
import logger from '../utils/logger';

const NotificationCenterContext = createContext(null);

export const ROLE_NOTIFICATION_TYPES = {
  doctor: [
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_changed',
    'schedule_change',
    'lab_results',
    'lab_critical_result',
    'system_alert'
  ],
  registrar: [
    'new_appointment',
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_changed',
    'queue_status_changed',
    'registrar_system_alert',
    'system_alert'
  ],
  lab: [
    'lab_new_study',
    'lab_critical_finding',
    'lab_result_sent_confirmation',
    'lab_results',
    'prescription_ready',
    'system_alert'
  ],
  patient: [
    'appointment_reminder',
    'appointment_rescheduled',
    'appointment_confirmation',
    'visit_confirmation',
    'payment_update',
    'payment_notification',
    'result_ready',
    'lab_results',
    'queue_changed'
  ],
  cardiologist: [
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_changed',
    'schedule_change',
    'lab_results',
    'lab_critical_result',
    'system_alert'
  ],
  dermatologist: [
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_changed',
    'schedule_change',
    'lab_results',
    'lab_critical_result',
    'system_alert'
  ],
  dentist: [
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_changed',
    'schedule_change',
    'lab_results',
    'lab_critical_result',
    'system_alert'
  ],
  admin: [
    'registrar_system_alert',
    'system_alert',
    'security_alert',
    'billing_alert',
    'queue_changed'
  ]
};

const TYPE_ALIASES = {
  queue_update: 'queue_changed',
  payment_notification: 'payment_notification',
  payment_success: 'payment_notification',
  appointment_confirmation: 'appointment_confirmation',
  appointment_reminder: 'appointment_reminder',
  schedule_change: 'schedule_change',
  visit_confirmation: 'visit_confirmation',
  lab_results: 'lab_results',
  prescription_ready: 'prescription_ready',
  system_alert: 'system_alert'
};

const EMPTY_UNREAD_SNAPSHOT = {
  total: 0,
  by_role: {},
  by_channel: {},
  by_severity: {}
};

const MAX_INBOX_ITEMS = 200;

function normalizeSlug(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');
}

function normalizeRole(role) {
  const normalized = normalizeSlug(role);
  return normalized || null;
}

function normalizeDepartmentKey(departmentKey) {
  const normalized = normalizeSlug(departmentKey);
  return normalized || null;
}

function normalizeNotificationType(type) {
  const normalized = normalizeSlug(type || 'notification');
  return TYPE_ALIASES[normalized] || normalized;
}

function inferRoleFromType(type) {
  const normalizedType = normalizeNotificationType(type);
  for (const [role, types] of Object.entries(ROLE_NOTIFICATION_TYPES)) {
    if (types.includes(normalizedType)) {
      return role;
    }
  }
  return null;
}

function extractItems(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }

  return (
    payload?.items ||
    payload?.results ||
    payload?.data ||
    payload?.notifications ||
    []
  );
}

function normalizeNotification(input, source = 'api') {
  const createdAt =
    input.created_at ||
    input.createdAt ||
    input.dispatched_at ||
    input.dispatchedAt ||
    input.first_delivered_at ||
    input.firstDeliveredAt ||
    new Date().toISOString();

  const type = normalizeNotificationType(
    input.type || input.event_type || input.notification_type || input.eventType
  );
  const role = normalizeRole(
    input.role || input.target_role || input.recipient_role || input.recipientType
  ) || inferRoleFromType(type);

  return {
    id: String(
      input.id ||
        input.delivery_id ||
        input.notification_id ||
        input.event_id ||
        `${source}-${Date.now()}-${Math.random()}`
    ),
    deliveryId: input.delivery_id || input.deliveryId || input.id || null,
    eventId: input.event_id || input.eventId || null,
    sequenceId: Number(input.sequence_id || input.sequenceId || 0),
    type,
    notificationType:
      input.notification_type || input.notificationType || input.event_type || type,
    eventType: input.event_type || input.eventType || type,
    title: input.title || input.subject || 'Уведомление',
    message: input.message || input.body || input.content || '',
    severity: input.severity || 'info',
    priority: input.priority || 'normal',
    recipientType: input.recipient_type || input.recipientType || null,
    recipientId: input.recipient_id || input.recipientId || null,
    role,
    departmentKey: normalizeDepartmentKey(
      input.department_key || input.departmentKey || input.department
    ),
    channel: input.channel || 'in_app_inbox',
    status: input.status || input.delivery_status || input.deliveryStatus || 'pending',
    deliveryStatus:
      input.delivery_status || input.deliveryStatus || input.status || 'pending',
    isRead: Boolean(
      input.is_read ?? input.isRead ?? input.read_at ?? input.readAt ?? false
    ),
    isSeen: Boolean(
      input.is_seen ?? input.isSeen ?? input.seen_at ?? input.seenAt ?? false
    ),
    isArchived: Boolean(
      input.is_archived ?? input.isArchived ?? input.archived_at ?? input.archivedAt ?? false
    ),
    correlationId: input.correlation_id || input.correlationId || null,
    dedupKey: input.dedup_key || input.dedupKey || null,
    deepLink: input.deep_link || input.deepLink || null,
    payloadSnapshot: input.payload_snapshot || input.payloadSnapshot || null,
    createdAt,
    dispatchedAt: input.dispatched_at || input.dispatchedAt || null,
    firstDeliveredAt: input.first_delivered_at || input.firstDeliveredAt || null,
    seenAt: input.seen_at || input.seenAt || null,
    readAt: input.read_at || input.readAt || null,
    archivedAt: input.archived_at || input.archivedAt || null,
    raw: input
  };
}

function mergeInboxItems(current, incoming) {
  const byId = new Map();

  for (const item of current) {
    byId.set(String(item.id), item);
  }

  for (const item of incoming) {
    const key = String(item.id);
    const existing = byId.get(key);
    if (!existing) {
      byId.set(key, item);
      continue;
    }

    byId.set(key, {
      ...existing,
      ...item,
      isRead: existing.isRead || item.isRead,
      isSeen: existing.isSeen || item.isSeen,
      isArchived: existing.isArchived || item.isArchived
    });
  }

  return Array.from(byId.values()).sort((a, b) => {
    const sequenceDiff = (Number(b.sequenceId) || 0) - (Number(a.sequenceId) || 0);
    if (sequenceDiff !== 0) {
      return sequenceDiff;
    }

    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  }).slice(0, MAX_INBOX_ITEMS);
}

function replaceItemState(item, patch) {
  return {
    ...item,
    ...patch
  };
}

function isUnread(item) {
  return !item.isRead && !item.isArchived;
}

function getUnreadSnapshotFromResponse(payload) {
  return {
    total: Number(payload?.total ?? 0),
    by_role: payload?.by_role || {},
    by_channel: payload?.by_channel || {},
    by_severity: payload?.by_severity || {}
  };
}

export function NotificationCenterProvider({ children }) {
  const [inbox, setInbox] = useState([]);
  const [unreadSnapshot, setUnreadSnapshot] = useState(EMPTY_UNREAD_SNAPSHOT);
  const [lastSyncAt, setLastSyncAt] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const replaceNotifications = useCallback((items, meta = {}) => {
    const normalized = items.map((item) => normalizeNotification(item, meta.source || 'api'));
    setInbox((current) => mergeInboxItems(current, normalized));
    if (meta.unreadSnapshot) {
      setUnreadSnapshot(meta.unreadSnapshot);
    }
    if (meta.lastSyncAt) {
      setLastSyncAt(meta.lastSyncAt);
    }
    return normalized;
  }, []);

  const refreshUnreadCounts = useCallback(
    async (params = {}) => {
      try {
        const payload = await notificationsService.getUnreadCount(params);
        const snapshot = getUnreadSnapshotFromResponse(payload);
        setUnreadSnapshot(snapshot);
        return snapshot;
      } catch (error) {
        logger.warn('[NotificationCenter] refreshUnreadCounts failed', error);
        return unreadSnapshot;
      }
    },
    [unreadSnapshot]
  );

  const syncNotifications = useCallback(
    async (params = {}) => {
      setIsLoading(true);
      try {
        const [inboxPayload, unreadPayload] = await Promise.all([
          notificationsService.getInbox(params),
          refreshUnreadCounts(params)
        ]);

        const items = extractItems(inboxPayload);
        const normalized = items.map((item) => normalizeNotification(item, 'api'));

        setInbox((current) => {
          const merged = mergeInboxItems(current, normalized);
          if (params.replace === true) {
            return normalized
              .concat(current.filter((item) => !normalized.some((next) => String(next.id) === String(item.id))))
              .sort((a, b) => {
                const sequenceDiff = (Number(b.sequenceId) || 0) - (Number(a.sequenceId) || 0);
                if (sequenceDiff !== 0) {
                  return sequenceDiff;
                }

                return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
              })
              .slice(0, MAX_INBOX_ITEMS);
          }
          return merged;
        });

        if (inboxPayload?.unread_count !== undefined && unreadPayload?.total === undefined) {
          setUnreadSnapshot((current) => ({
            ...current,
            total: Number(inboxPayload.unread_count || 0)
          }));
        }

        setLastSyncAt(new Date().toISOString());
        return normalized;
      } catch (error) {
        logger.error('[NotificationCenter] syncNotifications failed', error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [refreshUnreadCounts]
  );

  const loadNotifications = useCallback(
    async (params = {}) => syncNotifications(params),
    [syncNotifications]
  );

  const appendNotification = useCallback((event, source = 'ws') => {
    const normalized = normalizeNotification(event, source);
    setInbox((current) => {
      const existingIdx = current.findIndex((item) => String(item.id) === String(normalized.id));
      if (existingIdx >= 0) {
        const next = [...current];
        next[existingIdx] = replaceItemState(next[existingIdx], {
          ...normalized,
          isRead: next[existingIdx].isRead || normalized.isRead,
          isSeen: next[existingIdx].isSeen || normalized.isSeen,
          isArchived: next[existingIdx].isArchived || normalized.isArchived
        });
        return next;
      }

      if (isUnread(normalized)) {
        setUnreadSnapshot((currentSnapshot) => {
          const nextRole = normalized.role || 'unknown';
          return {
            ...currentSnapshot,
            total: currentSnapshot.total + 1,
            by_role: {
              ...currentSnapshot.by_role,
              [nextRole]: (currentSnapshot.by_role?.[nextRole] || 0) + 1
            }
          };
        });
      }

      return mergeInboxItems(current, [normalized]);
    });

    return normalized;
  }, []);

  const markAsSeen = useCallback(async (notificationId) => {
    setInbox((current) => current.map((item) => (
      String(item.id) === String(notificationId)
        ? replaceItemState(item, {
            isSeen: true,
            seenAt: new Date().toISOString(),
            deliveryStatus: item.deliveryStatus === 'pending' ? 'seen' : item.deliveryStatus,
            status: item.deliveryStatus === 'pending' ? 'seen' : item.status
          })
        : item
    )));

    try {
      const response = await notificationsService.markSeen(notificationId);
      await refreshUnreadCounts();
      return response;
    } catch (error) {
      logger.warn('[NotificationCenter] markAsSeen failed, resyncing inbox', error);
      await syncNotifications();
      throw error;
    }
  }, [refreshUnreadCounts, syncNotifications]);

  const markAsRead = useCallback(async (notificationId) => {
    setInbox((current) => current.map((item) => (
      String(item.id) === String(notificationId)
        ? replaceItemState(item, {
            isRead: true,
            isSeen: true,
            readAt: new Date().toISOString(),
            seenAt: item.seenAt || new Date().toISOString(),
            deliveryStatus: 'read',
            status: 'read'
          })
        : item
    )));

    try {
      const response = await notificationsService.markAsRead(notificationId);
      await refreshUnreadCounts();
      return response;
    } catch (error) {
      logger.warn('[NotificationCenter] markAsRead failed, resyncing inbox', error);
      await syncNotifications();
      throw error;
    }
  }, [refreshUnreadCounts, syncNotifications]);

  const archiveNotification = useCallback(async (notificationId) => {
    setInbox((current) => current.map((item) => (
      String(item.id) === String(notificationId)
        ? replaceItemState(item, {
            isArchived: true,
            isSeen: true,
            isRead: true,
            archivedAt: new Date().toISOString(),
            readAt: item.readAt || new Date().toISOString(),
            seenAt: item.seenAt || new Date().toISOString(),
            deliveryStatus: 'archived',
            status: 'archived'
          })
        : item
    )));

    try {
      const response = await notificationsService.archiveNotification(notificationId);
      await refreshUnreadCounts();
      return response;
    } catch (error) {
      logger.warn('[NotificationCenter] archiveNotification failed, resyncing inbox', error);
      await syncNotifications();
      throw error;
    }
  }, [refreshUnreadCounts, syncNotifications]);

  const markAllAsRead = useCallback(async (role = null, departmentKey = null) => {
    setInbox((current) => current.map((item) => {
      if (role && item.role && item.role !== normalizeRole(role)) {
        return item;
      }
      return replaceItemState(item, {
        isRead: true,
        isSeen: true,
        readAt: item.readAt || new Date().toISOString(),
        seenAt: item.seenAt || new Date().toISOString(),
        deliveryStatus: item.isArchived ? item.deliveryStatus : 'read',
        status: item.isArchived ? item.status : 'read'
      });
    }));

    try {
      const response = await notificationsService.markAllAsRead({
        role,
        department_key: departmentKey
      });
      await refreshUnreadCounts({ role, department_key: departmentKey });
      return response;
    } catch (error) {
      logger.warn('[NotificationCenter] markAllAsRead failed, resyncing inbox', error);
      await syncNotifications({ role, department_key: departmentKey });
      throw error;
    }
  }, [refreshUnreadCounts, syncNotifications]);

  const getNotificationsByRole = useCallback((role) => {
    const normalizedRole = normalizeRole(role);
    if (!normalizedRole) {
      return inbox;
    }

    const roleTypes = ROLE_NOTIFICATION_TYPES[normalizedRole] || [];
    return inbox.filter((item) => {
      if (item.role) {
        return item.role === normalizedRole;
      }
      if (!roleTypes.length) {
        return true;
      }
      return roleTypes.includes(item.type);
    });
  }, [inbox]);

  const getUnreadCount = useCallback((role = null) => {
    const normalizedRole = normalizeRole(role);
    if (!normalizedRole) {
      return unreadSnapshot.total || inbox.filter((item) => isUnread(item)).length;
    }

    const snapshotCount = unreadSnapshot.by_role?.[normalizedRole];
    if (typeof snapshotCount === 'number') {
      return snapshotCount;
    }

    return getNotificationsByRole(normalizedRole).filter((item) => isUnread(item)).length;
  }, [getNotificationsByRole, inbox, unreadSnapshot.by_role, unreadSnapshot.total]);

  const value = useMemo(() => ({
    inbox,
    unreadSnapshot,
    lastSyncAt,
    isLoading,
    replaceNotifications,
    appendNotification,
    loadNotifications,
    syncNotifications,
    refreshUnreadCounts,
    markAsSeen,
    markAsRead,
    archiveNotification,
    markAllAsRead,
    getNotificationsByRole,
    getUnreadCount
  }), [
    inbox,
    unreadSnapshot,
    lastSyncAt,
    isLoading,
    replaceNotifications,
    appendNotification,
    loadNotifications,
    syncNotifications,
    refreshUnreadCounts,
    markAsSeen,
    markAsRead,
    archiveNotification,
    markAllAsRead,
    getNotificationsByRole,
    getUnreadCount
  ]);

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
