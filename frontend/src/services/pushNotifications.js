import { useEffect, useState, useCallback } from 'react';
import logger from '../utils/logger';

/**
 * Push Notification Service
 * Handles browser push notifications for chat messages
 */

class PushNotificationService {
  constructor() {
    this.permission = 'default';
    this.isSupported = typeof window !== 'undefined' && 'Notification' in window;
    if (this.isSupported) {
      this.permission = Notification.permission;
    }
  }

  /**
   * Request notification permission from user
   */
  async requestPermission() {
    logger.log('[PushNotification] Requesting permission...');
    if (!this.isSupported) {
      logger.warn('Push notifications not supported');
      return false;
    }

    try {
      logger.log('[PushNotification] Calling Notification.requestPermission()');

      // Create a race between the permission request and a timeout
      const requestWithTimeout = new Promise((resolve) => {
        // Timeout after 10 seconds
        const timer = setTimeout(() => {
          logger.log('[PushNotification] Permission request timed out');
          resolve('timeout');
        }, 10000);

        (async () => {
          try {
            const permission = await Notification.requestPermission();
            clearTimeout(timer);
            resolve(permission);
          } catch (e) {
            clearTimeout(timer);
            logger.error('[PushNotification] Native request failed:', e);

            // Try callback fallback for older browsers inside the race
            try {
              Notification.requestPermission((perm) => {
                resolve(perm);
              });
            } catch {
              resolve('denied');
            }
          }
        })();
      });

      const permission = await requestWithTimeout;
      logger.log('[PushNotification] Permission result:', permission);

      if (permission === 'timeout') {
        return false;
      }

      this.permission = permission;
      return permission === 'granted';
    } catch (error) {
      logger.error('[PushNotification] Failed to request permission:', error);
      return false;
    }
  }

  /**
   * Check if notifications are enabled
   */
  isEnabled() {
    return this.isSupported && Notification.permission === 'granted';
  }

  /**
   * Show a notification for new message
   */
  showMessageNotification(message, senderName) {
    if (!this.isEnabled()) {
      return;
    }

    // Caller should decide if notification is needed based on focus/visibility
    // (Removing strict visibility check to allow notifications on dual monitors/split screen where tab is visible but not focused)
    // if (document.visibilityState === 'visible') {
    //     return;
    // }

    const title = `Новое сообщение от ${senderName || 'Пользователь'}`;
    const options = {
      body: message.message_type === 'voice' ?
      '🎤 Голосовое сообщение' :
      message.content?.substring(0, 100) || 'Новое сообщение',
      icon: '/favicon.ico',
      badge: '/favicon.ico',
      tag: `message-${message.id}`,
      renotify: true,
      requireInteraction: false,
      silent: false,
      data: {
        messageId: message.id,
        senderId: message.sender_id,
        url: window.location.origin
      }
    };

    try {
      const notification = new Notification(title, options);

      notification.onclick = () => {
        window.focus();
        notification.close();
        // Dispatch custom event to open chat with sender
        window.dispatchEvent(new CustomEvent('openChat', {
          detail: { userId: message.sender_id }
        }));
      };

      // Auto-close after 5 seconds
      setTimeout(() => notification.close(), 5000);
    } catch (error) {
      logger.error('[PushNotification] Failed to show notification:', error);
    }
  }


  /**
   * Show browser notification for operational/clinical events
   */
  showOperationalNotification(notification) {
    if (!this.isEnabled() || !notification) {
      return;
    }

    const title = notification.title || 'Уведомление';
    const options = {
      body: notification.message || 'Новое событие',
      icon: '/favicon.ico',
      badge: '/favicon.ico',
      tag: `ops-${notification.domain || 'system'}-${notification.id || Date.now()}`,
      renotify: true,
      requireInteraction: notification.type === 'critical' || notification.type === 'error',
      data: {
        domain: notification.domain,
        actionUrl: notification.action_url || null,
        payload: notification.payload || {}
      }
    };

    try {
      const browserNotification = new Notification(title, options);
      browserNotification.onclick = () => {
        window.focus();
        if (notification.action_url) {
          window.location.href = notification.action_url;
        }
        browserNotification.close();
      };
      setTimeout(() => browserNotification.close(), 7000);
    } catch (error) {
      logger.error('[PushNotification] Failed to show operational notification:', error);
    }
  }

  /**
   * Show notification for multiple unread messages
   */
  showUnreadCountNotification(count) {
    if (!this.isEnabled() || document.visibilityState === 'visible') {
      return;
    }

    if (count <= 0) return;

    const notification = new Notification(
      `У вас ${count} непрочитанных сообщений`,
      {
        icon: '/favicon.ico',
        tag: 'unread-count',
        renotify: false
      }
    );

    notification.onclick = () => {
      window.focus();
      notification.close();
    };
  }
}

// Singleton instance
export const pushNotifications = new PushNotificationService();

// React hook for push notifications
export function usePushNotifications() {
  const [isEnabled, setIsEnabled] = useState(false);
  const [isSupported] = useState(pushNotifications.isSupported);

  useEffect(() => {
    setIsEnabled(pushNotifications.isEnabled());
  }, []);

  const requestPermission = useCallback(async () => {
    const granted = await pushNotifications.requestPermission();
    setIsEnabled(granted);
    return granted;
  }, []);

  const showNotification = useCallback((message, senderName) => {
    pushNotifications.showMessageNotification(message, senderName);
  }, []);

  const showOperationalNotification = useCallback((notification) => {
    pushNotifications.showOperationalNotification(notification);
  }, []);

  return {
    isSupported,
    isEnabled,
    requestPermission,
    showNotification,
    showOperationalNotification
  };
}
