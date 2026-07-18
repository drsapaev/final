import React from 'react';
import type { CSSProperties } from 'react';

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
  Alert as AlertRaw,
  Badge,
  Button as ButtonRaw,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '../ui/macos';
import { usePWA } from '../../hooks/usePWA';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
const Button = ButtonRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Alert = AlertRaw as unknown as React.ComponentType<Record<string, unknown>>;
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

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

function CapabilityChipRaw({ children, icon: Icon, variant = 'outline', onClick, ariaLabel }: Record<string, unknown>) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const content = (
    <span style={styles.chipContent}>
      {Icon && React.createElement(Icon as unknown as React.ComponentType<Record<string, unknown>>, { size: 13, "aria-hidden": "true" })}
      {String(children)}
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
    <Badge variant={variant as unknown as "default" | "primary" | "secondary" | "success" | "warning" | "danger" | "info" | "outline"} size="small">
      {content}
    </Badge>
  );
}

CapabilityChipRaw.propTypes = {
  ariaLabel: PropTypes.string,
  children: PropTypes.node.isRequired,
  icon: PropTypes.elementType,
  onClick: PropTypes.func,
  variant: PropTypes.oneOf(['default', 'primary', 'secondary', 'success', 'warning', 'danger', 'info', 'outline'])
};

const CapabilityChip = CapabilityChipRaw as unknown as React.ComponentType<Record<string, unknown>>;

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

  const canRequestNotifications = (capabilities as Record<string, unknown>).notifications && notificationPermission !== 'granted';
  const title = updateAvailable ? t18('misc.pip_obnovlenie_dostupno') : t18('misc.pip_ustanovit_prilozhenie');
  const description = updateAvailable
    ? t18('misc.pip_dostupna_novaya_versiya_pril')
    : t18('misc.pip_ustanovite_prilozhenie_na_do');

  return (
    <div
      className="pwa-install-prompt"
      style={styles.shell as unknown as CSSProperties}
      role="dialog"
      aria-modal="false"
      aria-labelledby="pwa-install-prompt-title"
    >
      <Card variant="elevated" padding="default" style={styles.card as unknown as CSSProperties}>
        <CardHeader style={styles.header as unknown as CSSProperties}>
          <div style={styles.titleRow}>
            <Smartphone size={22} aria-hidden="true" style={styles.titleIcon} />
            <div>
              <CardTitle id="pwa-install-prompt-title" style={{ marginBottom: 2 } as CSSProperties}>
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
              aria-label={t18('misc.pip_zakryt_priglashenie_ustanovk')}
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
              <div style={styles.chipGrid as unknown as CSSProperties} aria-label={t18('misc.pip_statusy_pwa')}>
                <CapabilityChip
                  icon={isOnline ? CheckCircle2 : WifiOff}
                  variant={isOnline ? 'success' : 'warning'}
                >
                  {isOnline ? t18('misc.pip_onlayn') : t18('misc.pip_oflayn_rezhim')}
                </CapabilityChip>

                {(capabilities as Record<string, unknown>).notifications && (
                  <CapabilityChip
                    icon={Bell}
                    variant={notificationPermission === 'granted' ? 'success' : 'outline'}
                    onClick={canRequestNotifications ? handleNotificationPermission : undefined}
                    ariaLabel={t18('misc.pip_razreshit_push_uvedomleniya')}
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
                  {isInstalling ? t18('misc.pip_ustanovka') : t18('misc.pip_ustanovit_prilozhenie')}
                </Button>

                {(capabilities as Record<string, unknown>).notifications && notificationPermission === 'default' && (
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
            <p style={styles.capabilityLabel as unknown as CSSProperties}>{t18('misc.pip_vozmozhnosti_prilozheniya_2')}</p>
            <div style={styles.chipGrid as unknown as CSSProperties} aria-label={t18('misc.pip_vozmozhnosti_prilozheniya')}>
              {(capabilities as Record<string, unknown>).serviceWorker && (
                <CapabilityChip variant="outline">{t18('misc.pip_oflayn_rabota')}</CapabilityChip>
              )}
              {(capabilities as Record<string, unknown>).notifications && (
                <CapabilityChip variant="outline">{t18('misc.pip_uvedomleniya')}</CapabilityChip>
              )}
              {(capabilities as Record<string, unknown>).backgroundSync && (
                <CapabilityChip variant="outline">{t18('misc.pip_sinhronizatsiya')}</CapabilityChip>
              )}
              {(capabilities as Record<string, unknown>).webShare && (
                <CapabilityChip variant="outline">{t18('misc.pip_bystryy_dostup')}</CapabilityChip>
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
