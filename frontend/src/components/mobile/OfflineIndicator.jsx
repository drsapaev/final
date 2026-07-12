import { useState, useEffect } from 'react';
import { Wifi, WifiOff, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import { Card, Button } from '../ui/macos';
import { tokenManager } from '../../utils/tokenManager';
import logger from '../../utils/logger';
import { notify } from '../../services/notify.js';
/**
 * Индикатор офлайн/онлайн статуса для мобильных устройств
 */
const OfflineIndicator = () => {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [showIndicator, setShowIndicator] = useState(false);
  const [syncStatus, setSyncStatus] = useState('idle'); // idle, syncing, success, error
  const [cachedData, setCachedData] = useState({
    appointments: 0,
    patients: 0,
    notifications: 0
  });

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setShowIndicator(true);

      // Автоматически скрываем через 3 секунды
      setTimeout(() => {
        setShowIndicator(false);
      }, 3000);

      // Синхронизируем данные
      syncData();
    };

    const handleOffline = () => {
      setIsOnline(false);
      setShowIndicator(true);
      loadCachedData();
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Проверяем кэшированные данные при загрузке
    loadCachedData();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const loadCachedData = async () => {
    try {
      // PR-36 / P0-1: PHI localStorage cache removed for security.
      // Previously: cached_appointments / cached_patients / cached_notifications
      // were stored in plaintext localStorage — XSS or device theft would
      // expose patient PHI (ФИО, телефоны, записи).
      // Now: we only track whether the user has been online recently (a
      // non-PHI flag) and show the offline indicator. The mobile app can
      // re-fetch data from the server when connectivity is restored —
      // there is no real offline mode that justifies storing PHI locally.
      setCachedData({
        appointments: 0,
        patients: 0,
        notifications: 0
      });
    } catch (error) {
      logger.error('Ошибка загрузки кэшированных данных:', error);
    }
  };

  const syncData = async () => {
    setSyncStatus('syncing');

    try {
      // PR-36 / P0-1: Sync now only verifies connectivity + auth —
      // we no longer write PHI to localStorage. The mobile app refetches
      // data through the normal API hooks when it comes back online.
      const promises = [
      fetch('/api/v1/mobile/appointments', {
        headers: {
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        }
      }),
      fetch('/api/v1/mobile/notifications', {
        headers: {
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        }
      })];


      const responses = await Promise.allSettled(promises);

      // PR-36 / P0-1: removed the localStorage.setItem loop that wrote
      // PHI (appointments, notifications) to plaintext localStorage.
      // We now just count successful fetches for the UI indicator.
      const succeeded = responses.filter(
        (r) => r.status === 'fulfilled' && r.value.ok
      ).length;
      if (succeeded > 0) {
        logger.info(`Sync succeeded for ${succeeded}/${responses.length} endpoints`);
      }

      setSyncStatus('success');

      // Скрываем индикатор через 2 секунды
      setTimeout(() => {
        setShowIndicator(false);
        setSyncStatus('idle');
      }, 2000);

    } catch (error) {
      logger.error('Ошибка синхронизации:', error);
      setSyncStatus('error');

      setTimeout(() => {
        setSyncStatus('idle');
      }, 3000);
    }
  };

  const retryConnection = () => {
    if (navigator.onLine) {
      syncData();
    } else {
      // Показываем инструкции для восстановления подключения
      notify.warning('Проверьте подключение к интернету и попробуйте снова');
    }
  };

  if (!showIndicator && isOnline) {
    return null;
  }

  return (
    <div className="fixed top-4 left-4 right-4 z-50 md:left-auto md:right-4 md:max-w-sm">
      <Card className={`transition-all duration-300 ${isOnline ?
      'bg-green-50 border-green-200' :
      'bg-orange-50 border-orange-200'}`
      }>
        <div className="p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {isOnline ?
              <Wifi className="w-4 h-4 text-green-600" /> :

              <WifiOff className="w-4 h-4 text-orange-600" />
              }

              <span className={`font-medium text-sm ${isOnline ? 'text-green-800' : 'text-orange-800'}`
              }>
                {isOnline ? 'Подключение восстановлено' : 'Офлайн режим'}
              </span>

              {syncStatus === 'syncing' &&
              <RefreshCw className="w-3 h-3 text-blue-600 animate-spin" />
              }

              {syncStatus === 'success' &&
              <CheckCircle className="w-3 h-3 text-green-600" />
              }

              {syncStatus === 'error' &&
              <AlertCircle className="w-3 h-3 text-red-600" />
              }
            </div>

            {!isOnline &&
            <Button
              onClick={retryConnection}
              size="sm"
              variant="outline"
              className="text-xs">
              
                Повторить
              </Button>
            }
          </div>

          {!isOnline &&
          <div className="mt-2 text-xs text-orange-700">
              <p className="mb-1">Доступные данные в офлайн режиме:</p>
              <div className="flex space-x-4">
                {cachedData.appointments > 0 &&
              <span>📅 {cachedData.appointments} записей</span>
              }
                {cachedData.patients > 0 &&
              <span>👥 {cachedData.patients} пациентов</span>
              }
                {cachedData.notifications > 0 &&
              <span>🔔 {cachedData.notifications} уведомлений</span>
              }
              </div>
            </div>
          }

          {isOnline && syncStatus === 'success' &&
          <p className="mt-1 text-xs text-green-700">
              Данные синхронизированы
            </p>
          }

          {syncStatus === 'error' &&
          <p className="mt-1 text-xs text-red-700">
              Ошибка синхронизации
            </p>
          }
        </div>
      </Card>
    </div>);

};

export default OfflineIndicator;