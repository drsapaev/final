import { t } from '../../i18n/adapter';
import { useEffect, useState } from 'react';
import { Bell, X } from 'lucide-react';
import { pushNotifications } from '../../services/pushNotifications';
import notify from '../../services/notify';
import logger from '../../utils/logger';

/**
 * Prompt component to request push notification permission
 * Shows a non-intrusive banner that can be dismissed
 */
export function NotificationPrompt() {
  const [isVisible, setIsVisible] = useState(false);
  const [isEnabled, setIsEnabled] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);

  useEffect(() => {
    const canUseSessionStorage = typeof sessionStorage !== 'undefined';

    // Check if already dismissed this session
    const dismissed = canUseSessionStorage
      ? sessionStorage.getItem('notification-prompt-dismissed')
      : null;
    if (dismissed) {
      setIsDismissed(true);
      return;
    }

    // Check current permission status
    if (pushNotifications.isSupported) {
      const permission = typeof Notification !== 'undefined' ? Notification.permission : 'denied';
      if (permission === 'granted') {
        setIsEnabled(true);
      } else if (permission === 'default') {
        // Show prompt after 5 seconds
        const timer = setTimeout(() => setIsVisible(true), 5000);
        return () => clearTimeout(timer);
      }
    }
  }, []);

  const [isLoading, setIsLoading] = useState(false);

  const handleEnable = async () => {
    logger.log('[NotificationPrompt] Enable button clicked');
    setIsLoading(true);

    // Safety timeout to reset loading state if browser hangs
    let settled = false;
    const safetyTimer = setTimeout(() => {
      if (!settled) {
        logger.log('[NotificationPrompt] Request timed out or user ignored');
        setIsLoading(false);
        // Optionally close if we think they ignored it
      }
    }, 20000);

    try {
      const granted = await pushNotifications.requestPermission();
      settled = true;
      clearTimeout(safetyTimer);
      logger.log('[NotificationPrompt] Permission result:', granted);

      if (granted) {
        setIsEnabled(true);
        setIsVisible(false);
        // Show test notification
        if (typeof Notification !== 'undefined') {
          new Notification('Уведомления включены!', {
            body: 'Теперь вы будете получать уведомления о новых сообщениях',
            icon: '/favicon.ico'
          });
        }
      } else {
        // Permission denied or dismissed
        logger.log('[NotificationPrompt] Permission denied or dismissed');

        // If the user explicitly denied it (check current permission state)
        const permission = typeof Notification !== 'undefined' ? Notification.permission : 'denied';
        if (permission === 'denied') {
          notify.warning(t('final.notifications_blocked'));
        } else {
          // Just dismissed, or default
          logger.log('[NotificationPrompt] User dismissed the prompt');
        }

        setIsVisible(false);
      }
    } catch (error) {
      settled = true;
      clearTimeout(safetyTimer);
      logger.error('[NotificationPrompt] Error:', error);
      notify.error(t('final.notifications_enable_failed'));
    } finally {
      settled = true;
      setIsLoading(false);
    }
  };

  const handleDismiss = () => {
    setIsVisible(false);
    setIsDismissed(true);
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem('notification-prompt-dismissed', 'true');
    }
  };

  if (!isVisible || isDismissed || isEnabled) {
    return null;
  }

  return (
    <div className="notification-prompt">
      <div className="notification-prompt__content">
        <Bell className="notification-prompt__icon" size={20} />
        <div className="notification-prompt__text">
          <strong>Включить уведомления?</strong>
          <span>Получайте уведомления о новых сообщениях</span>
        </div>
      </div>
      <div className="notification-prompt__actions">
        <button
          className="notification-prompt__btn notification-prompt__btn--primary"
          onClick={handleEnable}
          disabled={isLoading}>
          
          {isLoading ? '...' : 'Включить'}
        </button>
        <button
          className="notification-prompt__btn notification-prompt__btn--secondary"
          onClick={handleDismiss}
          aria-label="Закрыть"
          disabled={isLoading}>
          
          <X size={16} />
        </button>
      </div>

      <style>{`
        .notification-prompt {
          position: fixed;
          bottom: 20px;
          right: 20px;
          background: linear-gradient(135deg, var(--mac-accent-purple) 0%, var(--mac-accent-purple) 100%);
          color: white;
          padding: 16px 20px;
          border-radius: 12px;
          box-shadow: 0 10px 40px rgba(102, 126, 234, 0.4);
          display: flex;
          align-items: center;
          gap: 16px;
          max-width: 400px;
          z-index: 10000;
          animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
          from {
            transform: translateY(100px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        
        .notification-prompt__content {
          display: flex;
          align-items: center;
          gap: 12px;
          flex: 1;
        }
        
        .notification-prompt__icon {
          flex-shrink: 0;
        }
        
        .notification-prompt__text {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        
        .notification-prompt__text strong {
          font-size: 14px;
        }
        
        .notification-prompt__text span {
          font-size: 12px;
          opacity: 0.9;
        }
        
        .notification-prompt__actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        
        .notification-prompt__btn {
          border: none;
          cursor: pointer;
          border-radius: 8px;
          font-weight: 500;
          transition: all 0.2s;
        }
        
        .notification-prompt__btn--primary {
          background: white;
          color: var(--mac-accent-purple);
          padding: 8px 16px;
          font-size: 13px;
        }
        
        .notification-prompt__btn--primary:hover {
          transform: scale(1.05);
        }
        
        .notification-prompt__btn--secondary {
          background: rgba(255, 255, 255, 0.2);
          color: white;
          padding: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        
        .notification-prompt__btn--secondary:hover {
          background: rgba(255, 255, 255, 0.3);
        }
      `}</style>
    </div>
  );

}

export default NotificationPrompt;
