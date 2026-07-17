import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import PropTypes from 'prop-types';
import { notificationsService } from '../api/services';
import logger from '../utils/logger';

// ---- Domain types ----
// The notification protocol is dynamic JSON from both WS push and REST
// poll. We model the canonical surface and let extra fields ride via the
// index signature.

type NotificationRole = 'doctor' | 'registrar' | 'lab' | 'patient' | 'dentist' | 'admin' | 'unknown' | string;
type NotificationSeverity = 'info' | 'warning' | 'error' | 'critical' | string;
type NotificationPriority = 'normal' | 'high' | 'low' | string;
type DeliveryStatus = 'pending' | 'seen' | 'read' | 'archived' | 'failed' | string | null;

type ByGroup = Record<string, number>;

interface UnreadSnapshot {
  total: number;
  by_role: ByGroup;
  by_channel: ByGroup;
  by_severity: ByGroup;
}

interface NormalizedNotification {
  id: string;
  deliveryId: string | number | null;
  eventId: string | number | null;
  sequenceId: number;
  type: string;
  notificationType: string;
  eventType: string;
  title: string;
  message: string;
  severity: NotificationSeverity;
  priority: NotificationPriority;
  recipientType: string | null;
  recipientId: string | number | null;
  role: NotificationRole | null;
  departmentKey: string | null;
  channel: string;
  status: DeliveryStatus;
  deliveryStatus: DeliveryStatus;
  isRead: boolean;
  isSeen: boolean;
  isArchived: boolean;
  correlationId: string | null;
  dedupKey: string | null;
  deepLink: string | null;
  payloadSnapshot: unknown;
  createdAt: string;
  dispatchedAt: string | null;
  firstDeliveredAt: string | null;
  seenAt: string | null;
  readAt: string | null;
  archivedAt: string | null;
  raw: unknown;
}

interface RawNotification {
  id?: string | number;
  delivery_id?: string | number;
  deliveryId?: string | number;
  notification_id?: string | number;
  event_id?: string | number;
  eventId?: string | number;
  sequence_id?: string | number;
  sequenceId?: string | number;
  type?: string;
  event_type?: string;
  notification_type?: string;
  eventType?: string;
  role?: string;
  target_role?: string;
  recipient_role?: string;
  recipientType?: string;
  recipient_type?: string;
  recipient_id?: string | number;
  recipientId?: string | number;
  department_key?: string;
  departmentKey?: string;
  department?: string;
  title?: string;
  subject?: string;
  message?: string;
  body?: string;
  content?: string;
  severity?: string;
  priority?: string;
  channel?: string;
  delivery_status?: string;
  deliveryStatus?: string;
  status?: string;
  is_read?: boolean;
  isRead?: boolean;
  read_at?: string;
  readAt?: string;
  is_seen?: boolean;
  isSeen?: boolean;
  seen_at?: string;
  seenAt?: string;
  is_archived?: boolean;
  isArchived?: boolean;
  archived_at?: string;
  archivedAt?: string;
  correlation_id?: string;
  correlationId?: string;
  dedup_key?: string;
  dedupKey?: string;
  deep_link?: string;
  deepLink?: string;
  payload_snapshot?: unknown;
  payloadSnapshot?: unknown;
  created_at?: string;
  createdAt?: string;
  dispatched_at?: string;
  dispatchedAt?: string;
  first_delivered_at?: string;
  firstDeliveredAt?: string;
  [key: string]: unknown;
}

interface InboxResponse {
  items?: RawNotification[];
  results?: RawNotification[];
  data?: RawNotification[];
  notifications?: RawNotification[];
  unread_count?: number;
  total?: number;
  by_role?: ByGroup;
  by_channel?: ByGroup;
  by_severity?: ByGroup;
  [key: string]: unknown;
}

interface UnreadCountResponse {
  total?: number;
  unread_count?: number;
  unreadCount?: number;
  by_role?: ByGroup;
  by_channel?: ByGroup;
  by_severity?: ByGroup;
  [key: string]: unknown;
}

interface SyncParams {
  replace?: boolean;
  role?: string | null;
  department_key?: string | null;
  [key: string]: unknown;
}

interface ReplaceNotificationsMeta {
  source?: string;
  unreadSnapshot?: UnreadSnapshot | Record<string, unknown>;
  lastSyncAt?: string;
}

interface UpdateUnreadSnapshotOptions {
  replace?: boolean;
}

interface NotificationCenterContextValue {
  inbox: NormalizedNotification[];
  unreadSnapshot: UnreadSnapshot;
  lastSyncAt: string | null;
  isLoading: boolean;
  replaceNotifications: (items: RawNotification[] | unknown[], meta?: ReplaceNotificationsMeta) => NormalizedNotification[];
  updateUnreadSnapshot: (snapshot: UnreadSnapshot | Record<string, unknown>, options?: UpdateUnreadSnapshotOptions) => void;
  appendNotification: (event: RawNotification | Record<string, unknown>, source?: string) => NormalizedNotification;
  loadNotifications: (params?: SyncParams) => Promise<NormalizedNotification[]>;
  syncNotifications: (params?: SyncParams) => Promise<NormalizedNotification[]>;
  refreshUnreadCounts: (params?: SyncParams) => Promise<UnreadSnapshot>;
  markAsSeen: (notificationId: string | number) => Promise<unknown>;
  markAsRead: (notificationId: string | number) => Promise<unknown>;
  archiveNotification: (notificationId: string | number) => Promise<unknown>;
  markAllAsRead: (role?: string | null, departmentKey?: string | null) => Promise<unknown>;
  getNotificationsByRole: (role: string | null) => NormalizedNotification[];
  getUnreadCount: (role?: string | null) => number;
}

interface NotificationCenterProviderProps {
  children: ReactNode;
}

const NotificationCenterContext = createContext<NotificationCenterContextValue | null>(null);

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

function normalizeSlug(value: unknown): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');
}

function normalizeRole(role: unknown): string | null {
  const normalized = normalizeSlug(role);
  return normalized || null;
}

function normalizeDepartmentKey(departmentKey: unknown): string | null {
  const normalized = normalizeSlug(departmentKey);
  return normalized || null;
}

function normalizeNotificationType(type: unknown): string {
  const normalized = normalizeSlug(type || 'notification');
  return TYPE_ALIASES[normalized] || normalized;
}

function inferRoleFromType(type: unknown): string | null {
  const normalizedType = normalizeNotificationType(type);
  for (const [role, types] of Object.entries(ROLE_NOTIFICATION_TYPES)) {
    if (types.includes(normalizedType)) {
      return role;
    }
  }
  return null;
}

function extractItems(payload: unknown): RawNotification[] {
  if (Array.isArray(payload)) {
    return payload as RawNotification[];
  }

  const p = (payload || {}) as InboxResponse;
  return (
    p.items ||
    p.results ||
    p.data ||
    p.notifications ||
    []
  );
}

function normalizeNotification(input: RawNotification | Record<string, unknown>, source = 'api'): NormalizedNotification {
  // Normalize the input shape: callers can pass either a typed
  // RawNotification or an arbitrary Record<string, unknown> (e.g. when
  // forwarding raw WS payloads). Cast to a unified accessor so property
  // reads resolve to concrete types instead of `unknown` from the
  // RawNotification index signature.
  const raw = input as RawNotification & Record<string, unknown>;
  const createdAt =
    raw.created_at ||
    raw.createdAt ||
    raw.dispatched_at ||
    raw.dispatchedAt ||
    raw.first_delivered_at ||
    raw.firstDeliveredAt ||
    new Date().toISOString();

  const type = normalizeNotificationType(
    raw.type || raw.event_type || raw.notification_type || raw.eventType
  );
  const role = normalizeRole(
    raw.role || raw.target_role || raw.recipient_role || raw.recipientType
  ) || inferRoleFromType(type);

  return {
    id: String(
      raw.id ||
        raw.delivery_id ||
        raw.notification_id ||
        raw.event_id ||
        `${source}-${Date.now()}-${Math.random()}`
    ),
    deliveryId: raw.delivery_id ?? raw.deliveryId ?? raw.id ?? null,
    eventId: raw.event_id ?? raw.eventId ?? null,
    sequenceId: Number(raw.sequence_id ?? raw.sequenceId ?? 0),
    type,
    notificationType: type,
    eventType: type,
    title: (raw.title as string) || (raw.subject as string) || 'Уведомление',
    message: (raw.message as string) || (raw.body as string) || (raw.content as string) || '',
    severity: (raw.severity as string) || 'info',
    priority: (raw.priority as string) || 'normal',
    recipientType: (raw.recipient_type as string) || (raw.recipientType as string) || null,
    recipientId: (raw.recipient_id as string | number) || (raw.recipientId as string | number) || null,
    role,
    departmentKey: normalizeDepartmentKey(
      (raw.department_key as string) || (raw.departmentKey as string) || (raw.department as string)
    ),
    channel: (raw.channel as string) || 'in_app_inbox',
    status: (raw.delivery_status as string) || (raw.deliveryStatus as string) || (raw.status as string) || null,
    deliveryStatus:
      (raw.delivery_status as string) || (raw.deliveryStatus as string) || (raw.status as string) || null,
    isRead: Boolean(
      raw.is_read ?? raw.isRead ?? raw.read_at ?? raw.readAt ?? false
    ),
    isSeen: Boolean(
      raw.is_seen ?? raw.isSeen ?? raw.seen_at ?? raw.seenAt ?? false
    ),
    isArchived: Boolean(
      raw.is_archived ?? raw.isArchived ?? raw.archived_at ?? raw.archivedAt ?? false
    ),
    correlationId: (raw.correlation_id as string) || (raw.correlationId as string) || null,
    dedupKey: (raw.dedup_key as string) || (raw.dedupKey as string) || null,
    deepLink: (raw.deep_link as string) || (raw.deepLink as string) || null,
    payloadSnapshot: raw.payload_snapshot ?? raw.payloadSnapshot ?? null,
    createdAt,
    dispatchedAt: (raw.dispatched_at as string) || (raw.dispatchedAt as string) || null,
    firstDeliveredAt: (raw.first_delivered_at as string) || (raw.firstDeliveredAt as string) || null,
    seenAt: (raw.seen_at as string) || (raw.seenAt as string) || null,
    readAt: (raw.read_at as string) || (raw.readAt as string) || null,
    archivedAt: (raw.archived_at as string) || (raw.archivedAt as string) || null,
    raw: input
  };
}

function mergeInboxItems(current: NormalizedNotification[], incoming: NormalizedNotification[]): NormalizedNotification[] {
  const byId = new Map<string, NormalizedNotification>();

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

function replaceItemState(item: NormalizedNotification, patch: Partial<NormalizedNotification>): NormalizedNotification {
  return {
    ...item,
    ...patch
  };
}

function isUnread(item: NormalizedNotification): boolean {
  return !item.isRead && !item.isArchived;
}

function getUnreadSnapshotFromResponse(payload: unknown): UnreadSnapshot {
  const p = (payload || {}) as UnreadCountResponse;
  const total =
    p?.total ??
    p?.unread_count ??
    p?.unreadCount ??
    0;

  return {
    total: Number(total),
    by_role: p?.by_role || {},
    by_channel: p?.by_channel || {},
    by_severity: p?.by_severity || {}
  };
}

export function applyUnreadSnapshot(
  currentSnapshot: UnreadSnapshot = EMPTY_UNREAD_SNAPSHOT,
  payload: Record<string, unknown> | UnreadSnapshot = {},
  replace = false
): UnreadSnapshot {
  const normalized = getUnreadSnapshotFromResponse(payload);
  const p = payload as UnreadCountResponse;
  const hasExplicitTotal =
    p?.total !== undefined ||
    p?.unread_count !== undefined ||
    p?.unreadCount !== undefined;

  if (replace) {
    return normalized;
  }

  return {
    total: hasExplicitTotal ? normalized.total : currentSnapshot.total,
    by_role: p?.by_role === undefined ? currentSnapshot.by_role : normalized.by_role,
    by_channel: p?.by_channel === undefined ? currentSnapshot.by_channel : normalized.by_channel,
    by_severity: p?.by_severity === undefined ? currentSnapshot.by_severity : normalized.by_severity
  };
}

export function NotificationCenterProvider({ children }: NotificationCenterProviderProps) {
  const [inbox, setInbox] = useState<NormalizedNotification[]>([]);
  const [unreadSnapshot, setUnreadSnapshot] = useState<UnreadSnapshot>(EMPTY_UNREAD_SNAPSHOT);
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const inboxRef = useRef<NormalizedNotification[]>(inbox);
  const unreadSnapshotRef = useRef<UnreadSnapshot>(unreadSnapshot);
  const unreadRefreshPromiseRef = useRef<Promise<UnreadSnapshot> | null>(null);
  const inboxSyncPromiseRef = useRef<Promise<NormalizedNotification[]> | null>(null);
  const unreadCooldownUntilRef = useRef<number>(0);
  const inboxCooldownUntilRef = useRef<number>(0);

  inboxRef.current = inbox;
  unreadSnapshotRef.current = unreadSnapshot;

  const replaceNotifications = useCallback((items: RawNotification[] | unknown[], meta: ReplaceNotificationsMeta = {}) => {
    const normalized = (items as RawNotification[]).map((item) => normalizeNotification(item, meta.source || 'api'));
    setInbox((current) => mergeInboxItems(current, normalized));
    if (meta.unreadSnapshot) {
      setUnreadSnapshot((current) => applyUnreadSnapshot(current, meta.unreadSnapshot as UnreadSnapshot, true));
    }
    if (meta.lastSyncAt) {
      setLastSyncAt(meta.lastSyncAt);
    }
    return normalized;
  }, []);

  const updateUnreadSnapshot = useCallback((snapshot: UnreadSnapshot | Record<string, unknown>, options: UpdateUnreadSnapshotOptions = {}) => {
    setUnreadSnapshot((current) => applyUnreadSnapshot(current, snapshot as UnreadSnapshot, options.replace === true));
  }, []);

  const refreshUnreadCounts = useCallback(
    async (params: SyncParams = {}) => {
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
          const err = error as { response?: { status?: number } };
          const status = err?.response?.status;
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
    async (params: SyncParams = {}) => {
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

        const inboxPayload = inboxResult.status === 'fulfilled' ? (inboxResult.value as InboxResponse) : null;
        const unreadPayload = unreadResult.status === 'fulfilled' ? (unreadResult.value as UnreadSnapshot) : null;

        if (inboxResult.status === 'rejected') {
          const inboxError = inboxResult.reason as { response?: { status?: number } };
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

        if (unreadResult.status === 'rejected' && ((unreadResult.reason as { response?: { status?: number } })?.response?.status === 429)) {
          unreadCooldownUntilRef.current = Date.now() + 60_000;
          logger.warn('[NotificationCenter] unread snapshot refresh rate limited, cooling down', {
            cooldownMs: 60_000,
            params
          });
        }

        setLastSyncAt(new Date().toISOString());
        return normalized;
      } catch (error) {
        const err = error as { response?: { status?: number } };
        const status = err?.response?.status;
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

      return inboxSyncPromiseRef.current as Promise<NormalizedNotification[]>;
    },
    [refreshUnreadCounts]
  );

  const loadNotifications = useCallback(
    async (params: SyncParams = {}) => syncNotifications(params),
    [syncNotifications]
  );

  const appendNotification = useCallback((event: RawNotification | Record<string, unknown>, source = 'ws') => {
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

  const markAsSeen = useCallback(async (notificationId: string | number) => {
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

  const markAsRead = useCallback(async (notificationId: string | number) => {
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

  const archiveNotification = useCallback(async (notificationId: string | number) => {
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

  const markAllAsRead = useCallback(async (role: string | null = null, departmentKey: string | null = null) => {
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

  const getNotificationsByRole = useCallback((role: string | null) => {
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

  const getUnreadCount = useCallback((role: string | null = null) => {
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

  const value = useMemo<NotificationCenterContextValue>(() => ({
    inbox,
    unreadSnapshot,
    lastSyncAt,
    isLoading,
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

export function useNotificationCenter(): NotificationCenterContextValue {
  const ctx = useContext(NotificationCenterContext);
  if (!ctx) {
    throw new Error('useNotificationCenter must be used within NotificationCenterProvider');
  }
  return ctx;
}
