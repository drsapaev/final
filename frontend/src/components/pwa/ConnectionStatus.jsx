import React, { useState, useEffect } from 'react';
import {
  Box,
  Chip,
  Alert,
  Snackbar,
  Typography,
  LinearProgress
} from '@mui/material';
import {
  Wifi,
  WifiOff,
  CloudDone,
  CloudOff,
  Sync,
  SyncDisabled
} from '@mui/icons-material';
import { usePWA } from '../../hooks/usePWA';

const ConnectionStatus = ({ showOfflineAlert = true, position = 'top' }) => {
  const { isOnline, isServiceWorkerReady } = usePWA();
  const [showOfflineSnackbar, setShowOfflineSnackbar] = useState(false);
  const [showOnlineSnackbar, setShowOnlineSnackbar] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);

  // Отслеживание изменений статуса подключения
  useEffect(() => {
    if (!isOnline && showOfflineAlert) {
      setShowOfflineSnackbar(true);
      setShowOnlineSnackbar(false);
    } else if (isOnline) {
      setShowOnlineSnackbar(true);
      setShowOfflineSnackbar(false);
      // Автоматически скрываем уведомление о восстановлении связи
      setTimeout(() => setShowOnlineSnackbar(false), 3000);
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
  }, []);

  const getConnectionIcon = () => {
    if (!isOnline) return <WifiOff />;
    if (isSyncing) return <Sync className="animate-spin" />;
    if (isServiceWorkerReady) return <CloudDone />;
    return <Wifi />;
  };

  const getConnectionColor = () => {
    if (!isOnline) return 'error';
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

  return (
    <>
      {/* Индикатор статуса */}
      <Box display="flex" alignItems="center" gap={1}>
        <Chip
          icon={getConnectionIcon()}
          label={getConnectionLabel()}
          color={getConnectionColor()}
          size="small"
          variant={isOnline ? "filled" : "outlined"}
        />
        
        {lastSyncTime && (
          <Typography variant="caption" color="text.secondary">
            Синхронизация: {formatLastSync()}
          </Typography>
        )}
      </Box>

      {/* Прогресс синхронизации */}
      {isSyncing && (
        <Box width="100%" mt={1}>
          <LinearProgress size="small" />
        </Box>
      )}

      {/* Уведомление об офлайн режиме */}
      <Snackbar
        open={showOfflineSnackbar}
        onClose={() => setShowOfflineSnackbar(false)}
        anchorOrigin={{ 
          vertical: position === 'top' ? 'top' : 'bottom', 
          horizontal: 'center' 
        }}
        autoHideDuration={null}
      >
        <Alert 
          severity="warning" 
          onClose={() => setShowOfflineSnackbar(false)}
          icon={<WifiOff />}
        >
          <Typography variant="body2" fontWeight="medium">
            Нет подключения к интернету
          </Typography>
          <Typography variant="caption" display="block">
            Приложение работает в офлайн режиме. Данные будут синхронизированы при восстановлении связи.
          </Typography>
        </Alert>
      </Snackbar>

      {/* Уведомление о восстановлении связи */}
      <Snackbar
        open={showOnlineSnackbar}
        onClose={() => setShowOnlineSnackbar(false)}
        anchorOrigin={{ 
          vertical: position === 'top' ? 'top' : 'bottom', 
          horizontal: 'center' 
        }}
        autoHideDuration={3000}
      >
        <Alert 
          severity="success" 
          onClose={() => setShowOnlineSnackbar(false)}
          icon={<CloudDone />}
        >
          <Typography variant="body2" fontWeight="medium">
            Подключение восстановлено
          </Typography>
          <Typography variant="caption" display="block">
            Синхронизация данных...
          </Typography>
        </Alert>
      </Snackbar>

      {/* Постоянный индикатор офлайн режима */}
      {!isOnline && (
        <Box 
          position="fixed" 
          top={0} 
          left={0} 
          right={0} 
          zIndex={1400}
          sx={{ 
            backgroundColor: 'warning.main',
            color: 'warning.contrastText',
            py: 0.5,
            px: 2,
            textAlign: 'center'
          }}
        >
          <Typography variant="caption" display="flex" alignItems="center" justifyContent="center" gap={1}>
            <WifiOff fontSize="small" />
            Офлайн режим - данные будут синхронизированы при подключении
          </Typography>
        </Box>
      )}
    </>
  );
};

export default ConnectionStatus;
