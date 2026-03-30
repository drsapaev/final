import { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import NotificationBell from './NotificationBell';
import NotificationInbox from './NotificationInbox';
import { useNotificationCenter } from '../../contexts/NotificationCenterContext';
import { getProfile } from '../../stores/auth';
import logger from '../../utils/logger';

export default function RoleNotificationCenter({ role }) {
  const [open, setOpen] = useState(false);
  const [recipientScope, setRecipientScope] = useState(null);
  const { loadNotifications, getUnreadCount } = useNotificationCenter();

  useEffect(() => {
    let isActive = true;

    const resolveRecipientScope = async () => {
      try {
        const profile = await getProfile();
        if (!isActive) {
          return;
        }

        if (!profile?.id) {
          logger.warn(`[NotificationCenter] missing auth profile for role=${role}`);
          return;
        }

        setRecipientScope({
          recipientId: profile.id,
          recipientType: role
        });
      } catch (error) {
        if (!isActive) {
          return;
        }

        logger.warn(`[NotificationCenter] failed to resolve recipient scope for role=${role}`, error);
      }
    };

    resolveRecipientScope();

    return () => {
      isActive = false;
    };
  }, [role]);

  const refreshNotifications = useCallback(() => {
    if (!recipientScope?.recipientId) {
      return Promise.resolve([]);
    }

    return loadNotifications({
      role,
      recipient_id: recipientScope.recipientId,
      recipient_type: recipientScope.recipientType,
      status: 'all',
      limit: 50
    });
  }, [loadNotifications, recipientScope, role]);

  useEffect(() => {
    refreshNotifications().catch((error) => {
      logger.warn(`[NotificationCenter] initial load failed for role=${role}`, error);
    });
  }, [refreshNotifications, role]);

  useEffect(() => {
    if (!open) {
      return;
    }

    refreshNotifications().catch((error) => {
      logger.warn(`[NotificationCenter] refresh load failed for role=${role}`, error);
    });
  }, [open, refreshNotifications, role]);

  return (
    <div style={{ position: 'fixed', top: 80, right: 24, zIndex: 1200 }}>
      <NotificationBell unreadCount={getUnreadCount(role)} onClick={() => setOpen((value) => !value)} />
      {open ? <NotificationInbox role={role} onClose={() => setOpen(false)} /> : null}
    </div>
  );
}

RoleNotificationCenter.propTypes = {
  role: PropTypes.oneOf([
    'doctor',
    'registrar',
    'lab',
    'patient',
    'cardiologist',
    'dermatologist',
    'dentist',
    'admin'
  ]).isRequired
};
