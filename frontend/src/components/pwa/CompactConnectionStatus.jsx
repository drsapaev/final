import { useState, useEffect } from 'react';
import { Wifi, WifiOff, Cloud, RefreshCw } from 'lucide-react';
import PropTypes from 'prop-types';
/**
 * Компактный индикатор подключения с PWA статусом
 * ИСПРАВЛЕНО: Убран избыточный импорт React
 */
const CompactConnectionStatus = ({ className = '', showTooltip = true }) => {
  const [isOnline, setIsOnline] = useState(() => (
    typeof navigator === 'undefined' ? true : navigator.onLine
  ));
  const [isServiceWorkerReady, setIsServiceWorkerReady] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState(null);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return undefined;
    }

    let cancelled = false;

    navigator.serviceWorker.ready
      .then(() => {
        if (!cancelled) {
          setIsServiceWorkerReady(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setIsServiceWorkerReady(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

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
  }, []);

  const getConnectionIcon = () => {
    if (!isOnline) return WifiOff;
    if (isSyncing) return RefreshCw;
    if (isServiceWorkerReady) return Cloud;
    return Wifi;
  };

  const getConnectionColor = () => {
    if (!isOnline) return 'var(--mac-error)'; // red-500
    if (isSyncing) return 'var(--mac-warning)'; // amber-500
    if (isServiceWorkerReady) return 'var(--mac-success)'; // emerald-500
    return 'var(--mac-accent-blue)'; // blue-500
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
  const color = getConnectionColor();
  const label = getConnectionLabel();
  const lastSync = formatLastSync();

  return (
    <div 
      className={`flex items-center gap-1 ${className}`}
      title={showTooltip ? `${label}${lastSync ? ` • Синхронизация: ${lastSync}` : ''}` : ''}
    >
      <Icon 
        size={16} 
        color={color}
        className={isSyncing ? 'animate-spin' : ''}
      />
      {showTooltip && (
        <span 
          className="text-xs font-medium"
          style={{ color }}
        >
          {label}
        </span>
      )}
    </div>
  );
};


CompactConnectionStatus.propTypes = {
  ...(CompactConnectionStatus.propTypes || {}),
  className: PropTypes.any,
  showTooltip: PropTypes.any,
};

export default CompactConnectionStatus;
