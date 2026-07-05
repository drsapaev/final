import PropTypes from 'prop-types';
import { Bell } from 'lucide-react';

export default function NotificationBell({ unreadCount = 0, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 44,
        height: 44,
        borderRadius: '50%',
        border: '1px solid var(--mac-border)',
        background: 'var(--mac-bg-primary)',
        color: 'var(--mac-text-primary)',
        cursor: 'pointer',
        boxShadow: 'var(--mac-shadow-sm)'
      }}
      aria-label="Открыть центр уведомлений"
    >
      <Bell size={20} />
      {unreadCount > 0 ? (
        <span
          style={{
            position: 'absolute',
            top: -3,
            right: -3,
            minWidth: 18,
            height: 18,
            padding: '0 5px',
            borderRadius: 10,
            background: 'var(--mac-error)',
            color: 'white',
            fontSize: 11,
            lineHeight: '18px',
            fontWeight: 700,
            textAlign: 'center'
          }}
        >
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      ) : null}
    </button>
  );
}

NotificationBell.propTypes = {
  unreadCount: PropTypes.number,
  onClick: PropTypes.func.isRequired
};
