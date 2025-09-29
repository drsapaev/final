import React, { useState, useEffect } from 'react';
import { Wifi, WifiOff, Cloud, Sync } from 'lucide-react';
import { usePWA } from '../../hooks/usePWA';

const CompactConnectionStatus = ({ className = '', showTooltip = true }) => {
  const { isOnline, isServiceWorkerReady } = usePWA();
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState(null);

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
    if (isSyncing) return Sync;
    if (isServiceWorkerReady) return Cloud;
    return Wifi;
  };

  const getConnectionColor = () => {
    if (!isOnline) return '#ef4444'; // red-500
    if (isSyncing) return '#f59e0b'; // amber-500
    if (isServiceWorkerReady) return '#10b981'; // emerald-500
    return '#3b82f6'; // blue-500
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

export default CompactConnectionStatus;
