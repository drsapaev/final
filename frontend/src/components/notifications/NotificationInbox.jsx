import { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { ROLE_NOTIFICATION_TYPES, useNotificationCenter } from '../../contexts/NotificationCenterContext';

function formatDate(value) {
  if (!value) return '';
  try {
    return new Date(value).toLocaleString('ru-RU');
  } catch {
    return value;
  }
}

export default function NotificationInbox({ role, onClose }) {
  const { getNotificationsByRole, markAsRead, markAllAsRead } = useNotificationCenter();
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const roleTypes = useMemo(() => ROLE_NOTIFICATION_TYPES[role] || [], [role]);

  const notifications = useMemo(() => {
    const scoped = getNotificationsByRole(role)
      .filter((item) => roleTypes.length === 0 || roleTypes.includes(item.type) || !item.role)
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    if (showUnreadOnly) {
      return scoped.filter((item) => !item.isRead);
    }
    return scoped;
  }, [getNotificationsByRole, role, roleTypes, showUnreadOnly]);

  return (
    <div
      style={{
        position: 'absolute',
        top: 52,
        right: 0,
        width: 380,
        maxHeight: 520,
        overflowY: 'auto',
        padding: 12,
        borderRadius: 12,
        border: '1px solid var(--mac-border)',
        background: 'var(--mac-bg-primary)',
        boxShadow: 'var(--mac-shadow-md)',
        zIndex: 30
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <strong>Уведомления</strong>
        <button type="button" onClick={onClose} style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}>✕</button>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <button type="button" onClick={() => setShowUnreadOnly((v) => !v)}>
          {showUnreadOnly ? 'Показать все' : 'Только непрочитанные'}
        </button>
        <button type="button" onClick={() => markAllAsRead(role)}>Прочитать все</button>
      </div>

      {notifications.length === 0 ? (
        <div style={{ color: 'var(--mac-text-secondary)', padding: 8 }}>Нет уведомлений по выбранной роли.</div>
      ) : (
        notifications.map((item) => (
          <button
            type="button"
            key={item.id}
            onClick={() => markAsRead(item.id)}
            style={{
              width: '100%',
              textAlign: 'left',
              border: '1px solid var(--mac-border)',
              borderRadius: 10,
              marginBottom: 8,
              padding: 10,
              background: item.isRead ? 'var(--mac-bg-secondary)' : 'rgba(59,130,246,0.08)',
              cursor: 'pointer'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>{item.title}</strong>
              {!item.isRead ? <span style={{ color: '#2563eb', fontSize: 12 }}>new</span> : null}
            </div>
            <div style={{ marginTop: 4, color: 'var(--mac-text-secondary)', fontSize: 13 }}>{item.message}</div>
            <div style={{ marginTop: 6, fontSize: 12, color: 'var(--mac-text-tertiary)' }}>{formatDate(item.createdAt)}</div>
          </button>
        ))
      )}
    </div>
  );
}

NotificationInbox.propTypes = {
  role: PropTypes.oneOf(['doctor', 'registrar', 'lab', 'patient']).isRequired,
  onClose: PropTypes.func.isRequired
};
