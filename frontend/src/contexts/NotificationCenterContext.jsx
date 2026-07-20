import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { notificationsService } from '../api/services';
import logger from '../utils/logger';

const NotificationCenterContext = createContext(null);

export const ROLE_NOTIFICATION_TYPES = {
  doctor: [
    'message_received',
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_update',
    'queue_call',
    'queue_position',
    'queue_reminder',
    'diagnostics_return_needed',
    'schedule_change',
    'lab_results',
    'lab_critical_result',
    'lab_result_sent_confirmation',
    'security_alert',
    'system_alert'
  ],
  registrar: [
    'new_appointment',
    'all_free_requested',
    'all_free_approved',
    'all_free_rejected',
    'message_received',
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_update',
    'queue_call',
    'queue_position',
    'queue_reminder',
    'queue_status_changed',
    'price_change',
    'patient_registered',
    'registrar_system_alert',
    'billing_alert',
    'security_alert',
    'system_alert'
  ],
  lab: [
    'lab_new_study',
    'diagnostics_return_needed',
    'lab_critical_finding',
    'lab_critical_result',
    'lab_result_sent_confirmation',
    'lab_results',
    'prescription_ready',
    'system_alert'
  ],
  patient: [
    'message_received',
    'all_free_approved',
    'all_free_rejected',
    'appointment_reminder',
    'schedule_change',
    'appointment_confirmation',
    'visit_confirmation',
    'payment_notification',
    'lab_results',
    'queue_update',
    'queue_call',
    'queue_position',
    'queue_reminder',
    'diagnostics_return_needed'
  ],
  cardiologist: [
    'message_received',
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_update',
    'queue_call',
    'queue_position',
    'queue_reminder',
    'diagnostics_return_needed',
    'schedule_change',
    'lab_results',
    'lab_critical_result',
    'lab_result_sent_confirmation',
    'system_alert'
  ],
  dermatologist: [
    'message_received',
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_update',
    'queue_call',
    'queue_position',
    'queue_reminder',
    'diagnostics_return_needed',
    'schedule_change',
    'lab_results',
    'lab_critical_result',
    'lab_result_sent_confirmation',
    'system_alert'
  ],
  dentist: [
    'message_received',
    'appointment_reminder',
    'appointment_confirmation',
    'visit_confirmation',
    'queue_update',
    'queue_call',
    'queue_position',
    'queue_reminder',
    'diagnostics_return_needed',
    'schedule_change',
    'lab_results',
    'lab_critical_result',
    'lab_result_sent_confirmation',
    'system_alert'
  ],
  admin: [
    'all_free_requested',
    'all_free_approved',
    'all_free_rejected',
    'message_received',
    'new_appointment',
    'price_change',
    'queue_status_changed',
    'patient_registered',
    'registrar_system_alert',
    'system_alert',
    'security_alert',
    'billing_alert',
    'queue_update',
    'queue_call',
    'queue_position',
    'queue_reminder'
  ]
};

const TYPE_ALIASES = {
  queue_changed: 'queue_update',
  diagnostics_return: 'diagnostics_return_needed',
  queue_status: 'queue_status_changed',
  payment_update: 'payment_notification',
  payment_success: 'payment_notification',
  result_ready: 'lab_results',
  appointment_rescheduled: 'schedule_change',
  appointment_cancelled: 'schedule_change',
  all_free_pending: 'all_free_requested',
  all_free_declined: 'all_free_rejected',
  allfree_requested: 'all_free_requested',
  allfree_approved: 'all_free_approved',
  allfree_rejected: 'all_free_rejected',
  notification_message_received: 'message_received',
  lab_result_ready: 'lab_results',
  lab_critical: 'lab_critical_result',
  lab_new_assignment: 'lab_new_study',
  lab_result_sent: 'lab_result_sent_confirmation',
  registrar_alert: 'registrar_system_alert',
  security_warning: 'security_alert',
  billing_warning: 'billing_alert',
  patient_create: 'patient_registered',
  payment_notification: 'payment_notification',
  queue_update: 'queue_update',
  queue_call: 'queue_call',
  queue_position: 'queue_position',
  queue_reminder: 'queue_reminder',
  diagnostics_return_needed: 'diagnostics_return_needed',
  all_free_requested: 'all_free_requested',
  all_free_approved: 'all_free_approved',
  all_free_rejected: 'all_free_rejected',
  message_received: 'message_received',
  new_appointment: 'new_appointment',
  price_change: 'price_change',
  queue_status_changed: 'queue_status_changed',
  patient_registered: 'patient_registered',
  appointment_confirmation: 'appointment_confirmation',
  appointment_reminder: 'appointment_reminder',
  schedule_change: 'schedule_change',
  visit_confirmation: 'visit_confirmation',
  lab_results: 'lab_results',
  lab_critical_result: 'lab_critical_result',
  lab_new_study: 'lab_new_study',
  lab_critical_finding: 'lab_critical_finding',
  lab_result_sent_confirmation: 'lab_result_sent_confirmation',
  prescription_ready: 'prescription_ready',
  registrar_system_alert: 'registrar_system_alert',
  security_alert: 'security_alert',
  billing_alert: 'billing_alert',
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
    notificationType: type,
    eventType: type,
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
    status: input.delivery_status || input.deliveryStatus || input.status || null,
    deliveryStatus:
      input.delivery_status || input.deliveryStatus || input.status || null,
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
  const total =
    payload?.total ??
    payload?.unread_count ??
    payload?.unreadCount ??
    0;

  return {
    total: Number(total),
    by_role: payload?.by_role || {},
    by_channel: payload?.by_channel || {},
    by_severity: payload?.by_severity || {}
  };
}

export function applyUnreadSnapshot(currentSnapshot = EMPTY_UNREAD_SNAPSHOT, payload = {}, replace = false) {
  const normalized = getUnreadSnapshotFromResponse(payload);
  const hasExplicitTotal =
    payload?.total !== undefined ||
    payload?.unread_count !== undefined ||
    payload?.unreadCount !== undefined;

  if (replace) {
    return normalized;
  }

  return {
    total: hasExplicitTotal ? normalized.total : currentSnapshot.total,
    by_role: payload?.by_role === undefined ? currentSnapshot.by_role : normalized.by_role,
    by_channel: payload?.by_channel === undefined ? currentSnapshot.by_channel : normalized.by_channel,
    by_severity: payload?.by_severity === undefined ? currentSnapshot.by_severity : normalized.by_severity
  };
}

export function NotificationCenterProvider({ children }) {
  const [inbox, setInbox] = useState([]);
  const [unreadSnapshot, setUnreadSnapshot] = useState(EMPTY_UNREAD_SNAPSHOT);
  const [lastSyncAt, setLastSyncAt] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [inboxOpen, setInboxOpen] = useState(false);
  const inboxRef = useRef(inbox);
  const unreadSnapshotRef = useRef(unreadSnapshot);
  const unreadRefreshPromiseRef = useRef(null);
  const inboxSyncPromiseRef = useRef(null);
  const unreadCooldownUntilRef = useRef(0);
  const inboxCooldownUntilRef = useRef(0);

  inboxRef.current = inbox;
  unreadSnapshotRef.current = unreadSnapshot;

  const replaceNotifications = useCallback((items, meta = {}) => {
    const normalized = items.map((item) => normalizeNotification(item, meta.source || 'api'));
    setInbox((current) => mergeInboxItems(current, normalized));
    if (meta.unreadSnapshot) {
      setUnreadSnapshot((current) => applyUnreadSnapshot(current, meta.unreadSnapshot, true));
    }
    if (meta.lastSyncAt) {
      setLastSyncAt(meta.lastSyncAt);
    }
    return normalized;
  }, []);

  const updateUnreadSnapshot = useCallback((snapshot, options = {}) => {
    setUnreadSnapshot((current) => applyUnreadSnapshot(current, snapshot, options.replace === true));
  }, []);

  const refreshUnreadCounts = useCallback(
    async (params = {}) => {
      const now = Date.now();
      if (now < unreadCooldownUntilRef.current) {
        logger.info('[NotificationCenter] unread refresh skipped during cooldown', {
          cooldownUntil: unreadCooldownUntilRef.current,
          params
        });
        return unreadSnapshotRef.current;
      }

      if (unreadRefreshPromiseRef.current) {
        return unreadRefreshPromiseRef.current;
      }

      unreadRefreshPromiseRef.current = (async () => {
        try {
          const payload = await notificationsService.getUnreadCount(params);
          const snapshot = getUnreadSnapshotFromResponse(payload);
          setUnreadSnapshot((current) => applyUnreadSnapshot(current, snapshot, true));
          unreadCooldownUntilRef.current = 0;
          return snapshot;
        } catch (error) {
          const status = error?.response?.status;
          if (status === 429) {
            unreadCooldownUntilRef.current = Date.now() + 60_000;
            logger.warn('[NotificationCenter] refreshUnreadCounts rate limited, cooling down', {
              cooldownMs: 60_000,
              params
            });
          } else {
            logger.warn('[NotificationCenter] refreshUnreadCounts failed', error);
          }
          return unreadSnapshotRef.current;
        } finally {
          unreadRefreshPromiseRef.current = null;
        }
      })();

      return unreadRefreshPromiseRef.current;
    },
    []
  );

  const syncNotifications = useCallback(
    async (params = {}) => {
      const now = Date.now();
      if (now < inboxCooldownUntilRef.current) {
        logger.info('[NotificationCenter] inbox sync skipped during cooldown', {
          cooldownUntil: inboxCooldownUntilRef.current,
          params
        });
        return inboxRef.current;
      }

      if (inboxSyncPromiseRef.current) {
        return inboxSyncPromiseRef.current;
      }

      inboxSyncPromiseRef.current = (async () => {
      setIsLoading(true);
      try {
        const [inboxResult, unreadResult] = await Promise.allSettled([
          notificationsService.getInbox(params),
          refreshUnreadCounts(params)
        ]);

        const inboxPayload = inboxResult.status === 'fulfilled' ? inboxResult.value : null;
        const unreadPayload = unreadResult.status === 'fulfilled' ? unreadResult.value : null;

        if (inboxResult.status === 'rejected') {
          const inboxError = inboxResult.reason;
          if (inboxError?.response?.status === 429) {
            inboxCooldownUntilRef.current = Date.now() + 60_000;
            unreadCooldownUntilRef.current = Date.now() + 60_000;
            logger.warn('[NotificationCenter] inbox sync rate limited, cooling down', {
              cooldownMs: 60_000,
              params
            });
            return inboxRef.current;
          }
          throw inboxError;
        }

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
          setUnreadSnapshot((current) => applyUnreadSnapshot(current, {
            total: Number(inboxPayload.unread_count || 0)
          }));
        }

        if (unreadResult.status === 'rejected' && unreadResult.reason?.response?.status === 429) {
          unreadCooldownUntilRef.current = Date.now() + 60_000;
          logger.warn('[NotificationCenter] unread snapshot refresh rate limited, cooling down', {
            cooldownMs: 60_000,
            params
          });
        }

        setLastSyncAt(new Date().toISOString());
        return normalized;
      } catch (error) {
        const status = error?.response?.status;
        if (status === 429) {
          inboxCooldownUntilRef.current = Date.now() + 60_000;
          unreadCooldownUntilRef.current = Date.now() + 60_000;
          logger.warn('[NotificationCenter] syncNotifications rate limited, cooling down', {
            cooldownMs: 60_000,
            params
          });
          return inboxRef.current;
        }
        logger.error('[NotificationCenter] syncNotifications failed', error);
        throw error;
      } finally {
        setIsLoading(false);
        inboxSyncPromiseRef.current = null;
      }
      })();

      return inboxSyncPromiseRef.current;
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
    inboxOpen,
    setInboxOpen,
    replaceNotifications,
    updateUnreadSnapshot,
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
    inboxOpen,
    setInboxOpen,
    replaceNotifications,
    updateUnreadSnapshot,
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
