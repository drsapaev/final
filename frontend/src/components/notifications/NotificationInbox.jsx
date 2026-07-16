import { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Archive,
  CheckCheck,
  Eye,
  Search,
  Sparkles
} from 'lucide-react';
import {
  Select,
  Input } from '../ui/macos';
import { useNotificationCenter } from '../../contexts/NotificationCenterContext';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const STATUS_FILTER_OPTIONS = [
  { value: 'all', label: '\u0412\u0441\u0435' },
  { value: 'unread', label: '\u041d\u0435\u043f\u0440\u043e\u0447\u0438\u0442\u0430\u043d\u043d\u044b\u0435' },
  { value: 'seen', label: '\u041f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u043d\u043d\u044b\u0435' },
  { value: 'archived', label: '\u0410\u0440\u0445\u0438\u0432' }
];

function formatDate(value) {
  if (!value) return '';
  try {
    return new Date(value).toLocaleString('ru-RU');
  } catch {
    return value;
  }
}

function getSeverityStyle(severity = 'info') {
  switch (String(severity).toLowerCase()) {
    case 'critical':
    case 'error':
      return { color: 'var(--mac-error)', background: 'color-mix(in srgb, var(--mac-error), transparent 88%)' };
    case 'warning':
      return { color: 'var(--mac-warning-active, var(--mac-warning))', background: 'color-mix(in srgb, var(--mac-warning), transparent 88%)' };
    case 'success':
      return { color: 'var(--mac-success, var(--mac-success, var(--mac-success, #15803d)))', background: 'color-mix(in srgb, var(--mac-success), transparent 88%)' };
    default:
      return { color: 'var(--mac-accent-blue-hover)', background: 'color-mix(in srgb, var(--mac-accent-blue), transparent 90%)' };
  }
}

function extractMetadata(item) {
  if (!item) {
    return {};
  }

  const payloadSnapshot = item.payloadSnapshot || item.raw?.payload_snapshot || item.raw?.payloadSnapshot;
  let snapshotData = payloadSnapshot;
  if (typeof snapshotData === 'string') {
    try {
      snapshotData = JSON.parse(snapshotData);
    } catch {
      snapshotData = null;
    }
  }

  const metadata =
    snapshotData?.metadata ||
    item.raw?.metadata ||
    item.raw?.data ||
    {};

  return metadata && typeof metadata === 'object' ? metadata : {};
}

function resolveNotificationTarget(item, userRole) {
  const explicitDeepLink = String(item?.deepLink || '').trim();
  if (explicitDeepLink) {
    return explicitDeepLink;
  }

  const type = String(item?.type || item?.eventType || '').trim().toLowerCase();
  const metadata = extractMetadata(item);

  switch (type) {
    case 'all_free_requested':
    case 'all_free_approved':
    case 'all_free_rejected':
      return '/admin/all-free-requests';
    case 'message_received':
      return metadata.conversation_id ? `/messages?conversation=${metadata.conversation_id}` : '/messages';
    case 'lab_results':
      return '/lab/results';
    case 'lab_critical_result':
      return '/lab/results?critical=1';
    case 'new_appointment':
    case 'queue_status_changed':
    case 'price_change':
      return '/registrar';
    case 'patient_registered':
      return '/registrar/patients';
    case 'queue_call':
    case 'queue_position':
    case 'queue_reminder':
    case 'queue_update':
    case 'queue_changed':
    case 'diagnostics_return_needed':
      return '/queue';
    case 'security_alert':
    case 'billing_alert':
      return '/admin';
    case 'registrar_system_alert':
      return '/registrar';
    case 'system_alert':
      return userRole === 'admin' ? '/admin' : '/registrar';
    default:
      return null;
  }
}

function navigateToNotificationTarget(target) {
  if (!target || typeof window === 'undefined') {
    return;
  }

  try {
    const current = `${window.location.pathname || ''}${window.location.search || ''}`;
    if (current === target) {
      return;
    }
    window.history.pushState({}, '', target);
    window.dispatchEvent(new PopStateEvent('popstate'));
  } catch (error) {
    logger.warn('[NotificationInbox] failed to navigate by notification target', error);
  }
}

export default function NotificationInbox({ userRole, onClose }) {
  const { t } = useTranslation();
  const {
    getNotificationsByRole,
    markAsRead,
    markAsSeen,
    archiveNotification,
    markAllAsRead
  } = useNotificationCenter();
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchText, setSearchText] = useState('');

  const notifications = useMemo(() => {
    const scoped = getNotificationsByRole(userRole);
    const query = searchText.trim().toLowerCase();

    return scoped
      .filter((item) => {
        if (showUnreadOnly && (item.isRead || item.isArchived)) {
          return false;
        }

        if (statusFilter === 'unread') {
          return !item.isRead && !item.isArchived;
        }

        if (statusFilter === 'archived') {
          return Boolean(item.isArchived);
        }

        if (statusFilter === 'seen') {
          return Boolean(item.isSeen) && !item.isRead && !item.isArchived;
        }

        return true;
      })
      .filter((item) => {
        if (!query) {
          return true;
        }

        return (
          String(item.title || '').toLowerCase().includes(query) ||
          String(item.message || '').toLowerCase().includes(query) ||
          String(item.type || '').toLowerCase().includes(query) ||
          String(item.eventType || '').toLowerCase().includes(query)
        );
      })
      .sort((a, b) => {
        const sequenceDiff = (Number(b.sequenceId) || 0) - (Number(a.sequenceId) || 0);
        if (sequenceDiff !== 0) {
          return sequenceDiff;
        }

        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      });
  }, [getNotificationsByRole, userRole, searchText, showUnreadOnly, statusFilter]);

  const unreadCount = useMemo(
    () => notifications.filter((item) => !item.isRead && !item.isArchived).length,
    [notifications]
  );

  const handleOpen = async (item) => {
    try {
      if (!item.isSeen) {
        await markAsSeen(item.id);
      }

      if (!item.isRead && !item.isArchived) {
        await markAsRead(item.id);
      }

      const target = resolveNotificationTarget(item, userRole);
      navigateToNotificationTarget(target);
    } catch (error) {
      logger.warn('[NotificationInbox] failed to mark notification open state', error);
    }
  };

  const handleArchive = async (item, event) => {
    event.stopPropagation();
    try {
      await archiveNotification(item.id);
    } catch (error) {
      logger.warn('[NotificationInbox] failed to archive notification', error);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllAsRead(userRole);
    } catch (error) {
      logger.warn('[NotificationInbox] failed to mark all notifications as read', error);
    }
  };

  return (
    <div
      role="dialog"
      aria-label={t('misc.ni_tsentr_uvedomleniy')}
      style={{
        position: 'absolute',
        top: 52,
        right: 0,
        width: 420,
        maxHeight: 560,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 16,
        border: '1px solid var(--mac-border)',
        background: 'var(--mac-bg-primary)',
        boxShadow: 'var(--mac-shadow-lg)',
        zIndex: 30
      }}
    >
      <div
        style={{
          padding: 14,
          borderBottom: '1px solid var(--mac-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12
        }}
      >
        <div>
          <strong style={{ display: 'block' }}>{t('misc.ni_uvedomleniya')}</strong>
          <span style={{ fontSize: 12, color: 'var(--mac-text-tertiary)' }}>
            {userRole || 'all'} · {unreadCount} unread
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          style={{
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            color: 'var(--mac-text-secondary)',
            fontSize: 18,
            lineHeight: 1
          }}
          aria-label={t('misc.ni_zakryt_tsentr_uvedomleniy')}
        >
          ✕
        </button>
      </div>

      <div style={{ padding: 14, borderBottom: '1px solid var(--mac-border)', display: 'grid', gap: 10 }}>
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 10px',
            borderRadius: 12,
            border: '1px solid var(--mac-border)',
            background: 'var(--mac-bg-secondary)'
          }}
        >
          <Search size={16} />
          <Input
            type="search"
            aria-label={t('misc.ni_poisk_po_uvedomleniyam')}
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder={t('misc.ni_poisk_po_uvedomleniyam')}
            style={{
              flex: 1,
              border: 'none',
              background: 'transparent',
              outline: 'none',
              color: 'var(--mac-text-primary)'
            }}
          />
        </label>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            type="button"
            onClick={() => setShowUnreadOnly((value) => !value)}
            style={{
              padding: '7px 10px',
              borderRadius: 999,
              border: '1px solid var(--mac-border)',
              background: showUnreadOnly ? 'rgba(29, 78, 216, 0.12)' : 'var(--mac-bg-secondary)',
              color: 'var(--mac-text-primary)',
              cursor: 'pointer'
            }}
          >
            {showUnreadOnly ? t('misc.ni_vse_uvedomleniya') : t('misc.ni_tolko_neprochitannye')}
          </button>

          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            options={STATUS_FILTER_OPTIONS}
            size="small"
            style={{ minWidth: 190 }}
            aria-label={'\u0424\u0438\u043b\u044c\u0442\u0440 \u043f\u043e \u0441\u0442\u0430\u0442\u0443\u0441\u0443'}
          ></Select>

          <button
            type="button"
            onClick={handleMarkAllRead}
            style={{
              padding: '7px 10px',
              borderRadius: 999,
              border: '1px solid var(--mac-border)',
              background: 'var(--mac-bg-secondary)',
              color: 'var(--mac-text-primary)',
              cursor: 'pointer'
            }}
          >
            Прочитать все
          </button>
        </div>
      </div>

      <div style={{ padding: 14, overflowY: 'auto', flex: 1 }}>
        {notifications.length === 0 ? (
          <div style={{ color: 'var(--mac-text-secondary)', padding: 16, textAlign: 'center' }}>
            Нет уведомлений по выбранным фильтрам.
          </div>
        ) : (
          notifications.map((item) => {
            const severityStyle = getSeverityStyle(item.severity);
            const Icon = item.isArchived ? Archive : item.isRead ? CheckCheck : item.isSeen ? Eye : Sparkles;

            return (
              <div
                key={item.id}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  display: 'grid',
                  gap: 8,
                  border: '1px solid var(--mac-border)',
                  borderRadius: 14,
                  marginBottom: 10,
                  padding: 12,
                  background: item.isRead ? 'var(--mac-bg-secondary)' : 'rgba(29, 78, 216, 0.08)',
                  cursor: 'pointer'
                }}
              >
                  <button
                  type="button"
                  onClick={() => void handleOpen(item)}
                  style={{
                    all: 'unset',
                    display: 'grid',
                    width: '100%',
                    textAlign: 'left',
                    gap: 8,
                    cursor: 'pointer'
                  }}
                  aria-label={t('misc.ni_otkryt_uvedomlenie_item_titl', { title: item.title })}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                      <span
                        aria-hidden="true"
                        style={{
                          width: 30,
                          height: 30,
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: 999,
                          background: severityStyle.background,
                          color: severityStyle.color,
                          flexShrink: 0
                        }}
                      >
                        <Icon size={16} />
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <strong style={{ display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {item.title}
                        </strong>
                        <span style={{ fontSize: 12, color: 'var(--mac-text-tertiary)' }}>
                          {item.type}
                        </span>
                      </div>
                    </div>

                    <span
                      style={{
                        alignSelf: 'start',
                        fontSize: 11,
                        padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
                        borderRadius: 999,
                        background: severityStyle.background,
                        color: severityStyle.color,
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em'
                      }}
                    >
                      {item.severity || 'info'}
                    </span>
                  </div>

                  <div style={{ color: 'var(--mac-text-secondary)', fontSize: 13, lineHeight: 1.45 }}>
                    {item.message}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: 12,
                      color: 'var(--mac-text-tertiary)'
                    }}
                  >
                    <span>{formatDate(item.createdAt)}</span>
                    <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      {!item.isSeen && !item.isArchived ? <span>new</span> : null}
                      {item.isArchived ? <span>archived</span> : null}
                    </span>
                  </div>
                </button>

                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  {!item.isRead && !item.isArchived ? (
                    <span
                      style={{
                        padding: '5px 8px',
                        borderRadius: 999,
                        border: '1px solid rgba(29, 78, 216, 0.2)',
                        background: 'rgba(29, 78, 216, 0.12)',
                        color: 'var(--mac-accent-blue-hover)',
                        fontSize: 11
                      }}
                    >
                      Непрочитано
                    </span>
                  ) : null}

                  {!item.isRead && !item.isArchived ? (
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        void handleOpen(item);
                      }}
                      style={{
                        border: 'none',
                        borderRadius: 999,
                        padding: '6px 10px',
                        background: 'rgba(29, 78, 216, 0.12)',
                        color: 'var(--mac-accent-blue-hover)',
                        cursor: 'pointer'
                      }}
                    >
                      Прочитать
                    </button>
                  ) : null}

                  {!item.isArchived ? (
                    <button
                      type="button"
                      onClick={(event) => void handleArchive(item, event)}
                      style={{
                        border: 'none',
                        borderRadius: 999,
                        padding: '6px 10px',
                        background: 'var(--mac-bg-tertiary)',
                        color: 'var(--mac-text-secondary)',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6
                      }}
                    >
                      <Archive size={14} />
                      Архив
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

NotificationInbox.propTypes = {
  userRole: PropTypes.oneOf([
    'doctor',
    'registrar',
    'lab',
    'patient',
    'cardiologist',
    'dermatologist',
    'dentist',
    'admin'
  ]).isRequired,
  onClose: PropTypes.func.isRequired
};
