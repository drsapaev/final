import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Cloud, RefreshCw, Wifi, WifiOff, X } from 'lucide-react';

import {
  Alert, Badge, Button,
} from '../ui/macos';
import { usePWA } from '../../hooks/usePWA';

const toneConfig = {
  primary: {
    badge: 'primary',
    alert: 'info',
    color: 'var(--mac-accent-blue, #007aff)'
  },
  success: {
    badge: 'success',
    alert: 'success',
    color: 'var(--mac-success, #34c759)'
  },
  warning: {
    badge: 'warning',
    alert: 'warning',
    color: 'var(--mac-warning, #ff9500)'
  },
  danger: {
    badge: 'danger',
    alert: 'warning',
    color: 'var(--mac-danger, #ff3b30)'
  }
};

const toastPositionStyle = (position) => ({
  position: 'fixed',
  top: position === 'top' ? 16 : 'auto',
  bottom: position === 'top' ? 'auto' : 16,
  left: '50%',
  transform: 'translateX(-50%)',
  zIndex: 1400,
  width: 'min(520px, calc(100vw - 32px))'
});

const styles = {
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap'
  },
  badgeContent: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6
  },
  syncLabel: {
    fontSize: 'var(--mac-font-size-xs, 12px)',
    color: 'var(--mac-text-secondary, #64748b)'
  },
  progressWrap: {
    width: '100%',
    marginTop: 8
  },
  progressTrack: {
    height: 4,
    borderRadius: 999,
    overflow: 'hidden',
    background: 'rgba(255, 149, 0, 0.16)',
    border: '1px solid rgba(255, 149, 0, 0.24)'
  },
  progressBar: {
    width: '42%',
    height: '100%',
    borderRadius: 999,
    background: 'var(--mac-warning, #ff9500)',
    animation: 'connection-status-sync 1s ease-in-out infinite alternate'
  },
  toastAlert: {
    boxShadow: '0 16px 44px rgba(15, 23, 42, 0.18)',
    backdropFilter: 'blur(14px)',
    WebkitBackdropFilter: 'blur(14px)'
  },
  toastContent: {
    display: 'grid',
    gridTemplateColumns: '20px 1fr auto',
    gap: 10,
    alignItems: 'start'
  },
  toastTitle: {
    margin: 0,
    fontSize: 'var(--mac-font-size-base, 14px)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary, #1e293b)'
  },
  toastDescription: {
    margin: '4px 0 0',
    fontSize: 'var(--mac-font-size-xs, 12px)',
    lineHeight: 1.4,
    color: 'var(--mac-text-secondary, #64748b)'
  },
  closeButton: {
    width: 28,
    height: 28,
    minHeight: 28,
    padding: 0
  },
  offlineBanner: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 1400,
    background: 'var(--mac-warning, #ff9500)',
    color: 'var(--mac-bg-primary)',
    padding: '6px 16px',
    textAlign: 'center'
  },
  offlineBannerInner: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    fontSize: 'var(--mac-font-size-xs, 12px)',
    fontWeight: 'var(--mac-font-weight-medium)',
    lineHeight: 1.4
  }
};

function ConnectionToast({ open, position, tone, icon: Icon, title, description, onClose }) {
  if (!open) {
    return null;
  }

  const config = toneConfig[tone] || toneConfig.primary;

  return (
    <div style={toastPositionStyle(position)}>
      <Alert
        severity={config.alert}
        role={tone === 'danger' || tone === 'warning' ? 'alert' : 'status'}
        aria-live={tone === 'danger' || tone === 'warning' ? 'assertive' : 'polite'}
        style={styles.toastAlert}
      >
        <div style={styles.toastContent}>
          <Icon size={18} aria-hidden="true" style={{ color: config.color, marginTop: 1 }} />
          <div>
            <p style={styles.toastTitle}>{title}</p>
            <p style={styles.toastDescription}>{description}</p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="small"
            aria-label="Закрыть уведомление"
            onClick={onClose}
            style={styles.closeButton}
          >
            <X size={14} aria-hidden="true" />
          </Button>
        </div>
      </Alert>
    </div>
  );
}

ConnectionToast.propTypes = {
  description: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  onClose: PropTypes.func.isRequired,
  open: PropTypes.bool.isRequired,
  position: PropTypes.oneOf(['top', 'bottom']).isRequired,
  title: PropTypes.string.isRequired,
  tone: PropTypes.oneOf(['primary', 'success', 'warning', 'danger']).isRequired
};

const ConnectionStatus = ({ showOfflineAlert = true, position = 'top' }) => {
  const { isOnline, isServiceWorkerReady } = usePWA();
  const [showOfflineToast, setShowOfflineToast] = useState(false);
  const [showOnlineToast, setShowOnlineToast] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);

  // Отслеживание изменений статуса подключения
  useEffect(() => {
    if (!isOnline && showOfflineAlert) {
      setShowOfflineToast(true);
      setShowOnlineToast(false);
    } else if (isOnline) {
      setShowOnlineToast(true);
      setShowOfflineToast(false);
      // Автоматически скрываем уведомление о восстановлении связи
      setTimeout(() => setShowOnlineToast(false), 3000);
    }
  }, [isOnline, showOfflineAlert]);

  // Слушаем сообщения от Service Worker о синхронизации
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      const handleMessage = (event) => {
        if (event.data && event.data.type === 'SYNC_COMPLETE') {
          setLastSyncTime(new Date(event.data.timestamp));
          setIsSyncing(false);
        } else if (event.data && event.data.type === 'SYNC_START') {
          setIsSyncing(true);
        }
      };

      navigator.serviceWorker.addEventListener('message', handleMessage);

      return () => {
        navigator.serviceWorker.removeEventListener('message', handleMessage);
      };
    }

    return undefined;
  }, []);

  const getConnectionIcon = () => {
    if (!isOnline) return WifiOff;
    if (isSyncing) return RefreshCw;
    if (isServiceWorkerReady) return Cloud;
    return Wifi;
  };

  const getConnectionTone = () => {
    if (!isOnline) return 'danger';
    if (isSyncing) return 'warning';
    if (isServiceWorkerReady) return 'success';
    return 'primary';
  };

  const getConnectionLabel = () => {
    if (!isOnline) return 'Офлайн';
    if (isSyncing) return 'Синхронизация...';
    if (isServiceWorkerReady) return 'Онлайн';
    return 'Подключение...';
  };

  const formatLastSync = () => {
    if (!lastSyncTime) return null;

    const now = new Date();
    const diffMs = now - lastSyncTime;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'только что';
    if (diffMins < 60) return `${diffMins} мин назад`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} ч назад`;

    return lastSyncTime.toLocaleDateString();
  };

  const Icon = getConnectionIcon();
  const tone = getConnectionTone();
  const label = getConnectionLabel();
  const toneStyle = toneConfig[tone] || toneConfig.primary;

  return (
    <>
      {/* Индикатор статуса */}
      <div style={styles.statusRow}>
        <Badge
          variant={toneStyle.badge}
          size="small"
          aria-label={`Статус подключения: ${label}`}
        >
          <span style={styles.badgeContent}>
            <Icon size={14} aria-hidden="true" />
            {label}
          </span>
        </Badge>

        {lastSyncTime && (
          <span style={styles.syncLabel}>
            Синхронизация: {formatLastSync()}
          </span>
        )}
      </div>

      {/* Прогресс синхронизации */}
      {isSyncing && (
        <div style={styles.progressWrap}>
          <div
            style={styles.progressTrack}
            role="progressbar"
            aria-label="Синхронизация данных"
          >
            <div style={styles.progressBar} />
          </div>
        </div>
      )}

      <ConnectionToast
        open={showOfflineToast}
        position={position}
        tone="warning"
        icon={WifiOff}
        title="Нет подключения к интернету"
        description="Приложение работает в офлайн режиме. Данные будут синхронизированы при восстановлении связи."
        onClose={() => setShowOfflineToast(false)}
      />

      <ConnectionToast
        open={showOnlineToast}
        position={position}
        tone="success"
        icon={Cloud}
        title="Подключение восстановлено"
        description="Синхронизация данных..."
        onClose={() => setShowOnlineToast(false)}
      />

      {/* Постоянный индикатор офлайн режима */}
      {!isOnline && (
        <div style={styles.offlineBanner} role="status" aria-live="polite">
          <span style={styles.offlineBannerInner}>
            <WifiOff size={14} aria-hidden="true" />
            Офлайн режим - данные будут синхронизированы при подключении
          </span>
        </div>
      )}

      <style>{`
        @keyframes connection-status-sync {
          from { transform: translateX(-12%); }
          to { transform: translateX(152%); }
        }

        @media (prefers-reduced-motion: reduce) {
          [role="progressbar"] > div {
            animation: none !important;
            transform: none !important;
            width: 100% !important;
          }
        }
      `}</style>
    </>
  );
};

ConnectionStatus.propTypes = {
  position: PropTypes.oneOf(['top', 'bottom']),
  showOfflineAlert: PropTypes.bool
};

export default ConnectionStatus;
