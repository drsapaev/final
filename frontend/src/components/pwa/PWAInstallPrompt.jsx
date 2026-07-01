import { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Bell,
  CheckCircle2,
  Download,
  RefreshCw,
  Smartphone,
  WifiOff,
  X
} from 'lucide-react';

import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '../ui/macos';
import { usePWA } from '../../hooks/usePWA';
import logger from '../../utils/logger';

const styles = {
  shell: {
    position: 'fixed',
    bottom: 16,
    left: 16,
    right: 16,
    zIndex: 1300,
    maxWidth: 400,
    margin: '0 auto',
    animation: 'pwa-install-prompt-in 180ms ease-out'
  },
  card: {
    boxShadow: '0 18px 52px rgba(15, 23, 42, 0.18)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)'
  },
  header: {
    display: 'grid',
    gridTemplateColumns: '1fr auto',
    gap: 12,
    alignItems: 'start',
    marginBottom: 14,
    paddingBottom: 12
  },
  titleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    minWidth: 0
  },
  titleIcon: {
    color: 'var(--mac-accent-blue, #007aff)',
    flex: '0 0 auto'
  },
  closeButton: {
    width: 28,
    height: 28,
    minHeight: 28,
    padding: 0
  },
  body: {
    display: 'grid',
    gap: 12
  },
  actions: {
    display: 'grid',
    gap: 8
  },
  chipGrid: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6
  },
  chipContent: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5
  },
  chipButton: {
    minHeight: 22,
    padding: '2px 8px',
    borderRadius: 999,
    fontSize: 11,
    gap: 5,
    whiteSpace: 'nowrap'
  },
  capabilityLabel: {
    margin: '2px 0 0',
    fontSize: 11,
    color: 'var(--mac-text-secondary, #64748b)'
  },
  actionIcon: {
    marginRight: 6
  }
};

const hasNotificationApi = () => typeof window !== 'undefined' && 'Notification' in window;

function CapabilityChip({ children, icon: Icon, variant = 'outline', onClick, ariaLabel }) {
  const content = (
    <span style={styles.chipContent}>
      {Icon && <Icon size={13} aria-hidden="true" />}
      {children}
    </span>
  );

  if (onClick) {
    return (
      <Button
        type="button"
        variant="outline"
        size="small"
        onClick={onClick}
        aria-label={ariaLabel}
        style={styles.chipButton}
      >
        {content}
      </Button>
    );
  }

  return (
    <Badge variant={variant} size="small">
      {content}
    </Badge>
  );
}

CapabilityChip.propTypes = {
  ariaLabel: PropTypes.string,
  children: PropTypes.node.isRequired,
  icon: PropTypes.elementType,
  onClick: PropTypes.func,
  variant: PropTypes.oneOf(['default', 'primary', 'secondary', 'success', 'warning', 'danger', 'info', 'outline'])
};

const PWAInstallPrompt = ({ onClose }) => {
  const {
    isInstallable,
    isInstalled,
    isOnline,
    updateAvailable,
    installPWA,
    updateServiceWorker,
    requestNotificationPermission,
    capabilities = {}
  } = usePWA();

  const [isInstalling, setIsInstalling] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState(
    hasNotificationApi() ? window.Notification.permission : 'not-supported'
  );

  const handleInstall = async () => {
    setIsInstalling(true);
    try {
      const success = await installPWA();
      if (success && onClose) {
        setTimeout(onClose, 1000);
      }
    } catch (error) {
      logger.error('Installation failed:', error);
    } finally {
      setIsInstalling(false);
    }
  };

  const handleUpdate = () => {
    updateServiceWorker();
  };

  const handleNotificationPermission = async () => {
    const permission = await requestNotificationPermission();
    setNotificationPermission(permission);
  };

  if (isInstalled && !updateAvailable) {
    return null;
  }

  const canRequestNotifications = capabilities.notifications && notificationPermission !== 'granted';
  const title = updateAvailable ? 'Обновление доступно' : 'Установить приложение';
  const description = updateAvailable
    ? 'Доступна новая версия приложения с улучшениями и исправлениями.'
    : 'Установите приложение на домашний экран для быстрого доступа и работы офлайн.';

  return (
    <div
      className="pwa-install-prompt"
      style={styles.shell}
      role="dialog"
      aria-modal="false"
      aria-labelledby="pwa-install-prompt-title"
    >
      <Card variant="elevated" padding="default" style={styles.card}>
        <CardHeader style={styles.header}>
          <div style={styles.titleRow}>
            <Smartphone size={22} aria-hidden="true" style={styles.titleIcon} />
            <div>
              <CardTitle id="pwa-install-prompt-title" style={{ marginBottom: 2 }}>
                {title}
              </CardTitle>
              <CardDescription>{description}</CardDescription>
            </div>
          </div>

          {onClose && (
            <Button
              type="button"
              variant="ghost"
              size="small"
              onClick={onClose}
              aria-label="Закрыть приглашение установки"
              style={styles.closeButton}
            >
              <X size={14} aria-hidden="true" />
            </Button>
          )}
        </CardHeader>

        <CardContent style={styles.body}>
          {updateAvailable ? (
            <Button type="button" variant="primary" fullWidth onClick={handleUpdate}>
              <RefreshCw size={16} aria-hidden="true" style={styles.actionIcon} />
              Обновить приложение
            </Button>
          ) : isInstallable ? (
            <>
              <div style={styles.chipGrid} aria-label="Статусы PWA">
                <CapabilityChip
                  icon={isOnline ? CheckCircle2 : WifiOff}
                  variant={isOnline ? 'success' : 'warning'}
                >
                  {isOnline ? 'Онлайн' : 'Офлайн режим'}
                </CapabilityChip>

                {capabilities.notifications && (
                  <CapabilityChip
                    icon={Bell}
                    variant={notificationPermission === 'granted' ? 'success' : 'outline'}
                    onClick={canRequestNotifications ? handleNotificationPermission : undefined}
                    ariaLabel="Разрешить push уведомления"
                  >
                    Push уведомления
                  </CapabilityChip>
                )}
              </div>

              <div style={styles.actions}>
                <Button
                  type="button"
                  variant="primary"
                  onClick={handleInstall}
                  disabled={isInstalling}
                  fullWidth
                >
                  <Download size={16} aria-hidden="true" style={styles.actionIcon} />
                  {isInstalling ? 'Установка...' : 'Установить приложение'}
                </Button>

                {capabilities.notifications && notificationPermission === 'default' && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleNotificationPermission}
                    size="small"
                  >
                    <Bell size={14} aria-hidden="true" style={styles.actionIcon} />
                    Разрешить уведомления
                  </Button>
                )}
              </div>
            </>
          ) : (
            <Alert severity="info" role="status">
              Приложение уже установлено или не поддерживается вашим браузером.
            </Alert>
          )}

          <div>
            <p style={styles.capabilityLabel}>Возможности приложения:</p>
            <div style={styles.chipGrid} aria-label="Возможности приложения">
              {capabilities.serviceWorker && (
                <CapabilityChip variant="outline">Офлайн работа</CapabilityChip>
              )}
              {capabilities.notifications && (
                <CapabilityChip variant="outline">Уведомления</CapabilityChip>
              )}
              {capabilities.backgroundSync && (
                <CapabilityChip variant="outline">Синхронизация</CapabilityChip>
              )}
              {capabilities.webShare && (
                <CapabilityChip variant="outline">Быстрый доступ</CapabilityChip>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <style>{`
        @keyframes pwa-install-prompt-in {
          from {
            opacity: 0;
            transform: translateY(12px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .pwa-install-prompt {
            animation: none !important;
          }
        }
      `}</style>
    </div>
  );
};

PWAInstallPrompt.propTypes = {
  onClose: PropTypes.func
};

export default PWAInstallPrompt;
