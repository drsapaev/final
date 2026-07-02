import { useCallback, useEffect, useState } from 'react';
import { useRef } from 'react';
import PropTypes from 'prop-types';
import NotificationBell from './NotificationBell';
import NotificationInbox from './NotificationInbox';
import { useNotificationCenter } from '../../contexts/NotificationCenterContext';
import { getProfile } from '../../stores/auth';
import logger from '../../utils/logger';

export default function RoleNotificationCenter({ userRole }) {
  const [open, setOpen] = useState(false);
  const [recipientScope, setRecipientScope] = useState(null);
  const { loadNotifications, getUnreadCount } = useNotificationCenter();
  const lastLoadKeyRef = useRef(null);
  const lastLoadAtRef = useRef(0);

  const shouldSkipLoad = useCallback((scope, source) => {
    if (!scope?.recipientId) {
      return true;
    }

    const loadKey = `${userRole}:${scope.recipientId}:${scope.recipientType || 'unknown'}`;
    const now = Date.now();
    const withinCooldown = lastLoadKeyRef.current === loadKey && (now - lastLoadAtRef.current) < 15_000;

    if (withinCooldown) {
      logger.info('[FIX:NOTIFICATIONS] skipping duplicate role notification load', {
        role: userRole,
        source,
        loadKey,
        ageMs: now - lastLoadAtRef.current
      });
      return true;
    }

    lastLoadKeyRef.current = loadKey;
    lastLoadAtRef.current = now;
    return false;
  }, [userRole]);

  const runLoadNotifications = useCallback((source) => {
    if (shouldSkipLoad(recipientScope, source)) {
      return Promise.resolve([]);
    }

    return loadNotifications({
      role: userRole,
      recipient_id: recipientScope.recipientId,
      recipient_type: recipientScope.recipientType,
      status: 'all',
      limit: 50
    });
  }, [loadNotifications, recipientScope, userRole, shouldSkipLoad]);

  useEffect(() => {
    let isActive = true;

    const resolveRecipientScope = async () => {
      try {
        const profile = await getProfile();
        if (!isActive) {
          return;
        }

        if (!profile?.id) {
          logger.warn(`[NotificationCenter] missing auth profile for role=${userRole}`);
          return;
        }

        setRecipientScope({
          recipientId: profile.id,
          recipientType: userRole
        });
      } catch (error) {
        if (!isActive) {
          return;
        }

        logger.warn(`[NotificationCenter] failed to resolve recipient scope for role=${userRole}`, error);
      }
    };

    resolveRecipientScope();

    return () => {
      isActive = false;
    };
  }, [userRole]);

  const refreshNotifications = useCallback(() => {
    return runLoadNotifications('manual');
  }, [runLoadNotifications]);

  useEffect(() => {
    runLoadNotifications('initial').catch((error) => {
      logger.warn(`[NotificationCenter] initial load failed for role=${userRole}`, error);
    });
  }, [runLoadNotifications, userRole]);

  useEffect(() => {
    if (!open) {
      return;
    }

    runLoadNotifications('open').catch((error) => {
      logger.warn(`[NotificationCenter] refresh load failed for role=${userRole}`, error);
    });
  }, [open, runLoadNotifications, userRole]);

  return (
    <div style={{ position: 'fixed', top: 80, right: 24, zIndex: 1200 }}>
      <NotificationBell unreadCount={getUnreadCount(userRole)} onClick={() => setOpen((value) => !value)} />
      {open ? <NotificationInbox userRole={userRole} onClose={() => setOpen(false)} /> : null}
    </div>
  );
}

RoleNotificationCenter.propTypes = {
  userRole: PropTypes.oneOf([
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
