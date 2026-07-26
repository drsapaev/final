import { useCallback, useEffect, useState, useRef } from 'react';
import PropTypes from 'prop-types';
import NotificationInbox from './NotificationInbox';
import { useNotificationCenter } from '../../contexts/NotificationCenterContext';
import { getProfile } from '../../stores/auth';
import logger from '../../utils/logger';

/**
 * GlobalNotificationCenter — renders the notification inbox dropdown
 * when `inboxOpen` is true in NotificationCenterContext.
 *
 * Unlike RoleNotificationCenter (which was per-page with its own bell),
 * this component lives in AppShell and is controlled by the header bell
 * via the context's `setInboxOpen` function.
 *
 * The user's role is resolved from the auth store, not a prop, so this
 * component works on ALL pages without per-page configuration.
 */
export default function GlobalNotificationCenter() {
  const { inboxOpen, setInboxOpen, loadNotifications, getUnreadCount } = useNotificationCenter();
  const [recipientScope, setRecipientScope] = useState(null);
  const lastLoadKeyRef = useRef(null);
  const lastLoadAtRef = useRef(0);

  const shouldSkipLoad = useCallback((scope, source) => {
    if (!scope?.recipientId) {
      return true;
    }

    const loadKey = `${scope.recipientType || 'unknown'}:${scope.recipientId}`;
    const now = Date.now();
    const withinCooldown = lastLoadKeyRef.current === loadKey && (now - lastLoadAtRef.current) < 15_000;

    if (withinCooldown) {
      logger.info('[GlobalNotificationCenter] skipping duplicate load', { source, loadKey, ageMs: now - lastLoadAtRef.current });
      return true;
    }

    lastLoadKeyRef.current = loadKey;
    lastLoadAtRef.current = now;
    return false;
  }, []);

  const runLoadNotifications = useCallback((source) => {
    if (shouldSkipLoad(recipientScope, source)) {
      return Promise.resolve([]);
    }

    return loadNotifications({
      role: recipientScope.recipientType,
      recipient_id: recipientScope.recipientId,
      recipient_type: recipientScope.recipientType,
      status: 'all',
      limit: 50
    });
  }, [loadNotifications, recipientScope, shouldSkipLoad]);

  // Resolve the user's role + ID from auth store on mount
  useEffect(() => {
    let isActive = true;

    const resolveRecipientScope = async () => {
      try {
        const profile = await getProfile();
        if (!isActive) return;

        if (!profile?.id) {
          logger.warn('[GlobalNotificationCenter] missing auth profile');
          return;
        }

        const role = String(profile.role || profile.role_name || 'unknown').toLowerCase();
        const normalizedRole = role === 'receptionist' ? 'registrar' : role;

        setRecipientScope({
          recipientId: profile.id,
          recipientType: normalizedRole
        });
      } catch (error) {
        if (!isActive) return;
        logger.warn('[GlobalNotificationCenter] failed to resolve recipient scope', error);
      }
    };

    resolveRecipientScope();

    return () => { isActive = false; };
  }, []);

  // Initial load when recipient scope is resolved
  useEffect(() => {
    if (!recipientScope) return;
    runLoadNotifications('initial').catch((error) => {
      logger.warn('[GlobalNotificationCenter] initial load failed', error);
    });
  }, [runLoadNotifications, recipientScope]);

  // Refresh when inbox opens
  useEffect(() => {
    if (!inboxOpen) return;
    runLoadNotifications('open').catch((error) => {
      logger.warn('[GlobalNotificationCenter] refresh load failed', error);
    });
  }, [inboxOpen, runLoadNotifications]);

  if (!inboxOpen || !recipientScope) return null;

  return (
    <NotificationInbox
      userRole={recipientScope.recipientType}
      onClose={() => setInboxOpen(false)}
    />
  );
}

GlobalNotificationCenter.propTypes = {};
