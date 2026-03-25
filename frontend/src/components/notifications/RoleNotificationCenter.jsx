import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import NotificationBell from './NotificationBell';
import NotificationInbox from './NotificationInbox';
import { useNotificationCenter } from '../../contexts/NotificationCenterContext';
import logger from '../../utils/logger';

export default function RoleNotificationCenter({ role }) {
  const [open, setOpen] = useState(false);
  const { loadNotifications, getUnreadCount } = useNotificationCenter();

  useEffect(() => {
    loadNotifications({ role }).catch((error) => {
      logger.warn(`[NotificationCenter] initial load failed for role=${role}`, error);
    });
  }, [loadNotifications, role]);

  return (
    <div style={{ position: 'fixed', top: 80, right: 24, zIndex: 1200 }}>
      <NotificationBell unreadCount={getUnreadCount(role)} onClick={() => setOpen((v) => !v)} />
      {open ? <NotificationInbox role={role} onClose={() => setOpen(false)} /> : null}
    </div>
  );
}

RoleNotificationCenter.propTypes = {
  role: PropTypes.oneOf(['doctor', 'registrar', 'lab', 'patient']).isRequired
};
