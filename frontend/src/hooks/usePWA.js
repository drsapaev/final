import { useState, useEffect, useCallback } from 'react';
import { initializePWA, isPWAInstalled, getConnectionInfo } from '../utils/pwa';

/**
 * Хук для работы с PWA функциями
 */
export const usePWA = () => {
  const [isInstalled, setIsInstalled] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [connectionInfo, setConnectionInfo] = useState(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Инициализация PWA
  useEffect(() => {
    const init = async () => {
      try {
        await initializePWA();
        setIsInitialized(true);
      } catch (error) {
        console.error('Ошибка инициализации PWA:', error);
      }
    };

    init();
  }, []);

  // Проверка установки PWA
  useEffect(() => {
    const checkInstallation = () => {
      setIsInstalled(isPWAInstalled());
    };

    checkInstallation();
    
    // Проверяем при изменении размера окна (может измениться режим отображения)
    window.addEventListener('resize', checkInstallation);
    
    return () => {
      window.removeEventListener('resize', checkInstallation);
    };
  }, []);

  // Отслеживание статуса подключения
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setConnectionInfo(getConnectionInfo());
    };

    const handleOffline = () => {
      setIsOnline(false);
      setConnectionInfo(null);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Инициальная проверка
    setConnectionInfo(getConnectionInfo());

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Функция для проверки поддержки функций
  const checkSupport = useCallback(() => {
    return {
      serviceWorker: 'serviceWorker' in navigator,
      pushManager: 'PushManager' in window,
      notification: 'Notification' in window,
      backgroundSync: 'serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype,
      cache: 'caches' in window,
      indexedDB: 'indexedDB' in window,
      installPrompt: 'onbeforeinstallprompt' in window
    };
  }, []);

  // Функция для получения информации о подключении
  const getConnectionDetails = useCallback(() => {
    return {
      isOnline,
      connectionInfo,
      effectiveType: connectionInfo?.effectiveType || 'unknown',
      downlink: connectionInfo?.downlink || 0,
      rtt: connectionInfo?.rtt || 0,
      saveData: connectionInfo?.saveData || false
    };
  }, [isOnline, connectionInfo]);

  // Функция для проверки, нужно ли показывать промпт установки
  const shouldShowInstallPrompt = useCallback(() => {
    if (isInstalled) return false;
    
    // Проверяем, не отклонил ли пользователь ранее
    const wasDismissed = localStorage.getItem('pwa-install-dismissed');
    if (wasDismissed) return false;
    
    return true;
  }, [isInstalled]);

  // Функция для отметки промпта как отклоненного
  const dismissInstallPrompt = useCallback(() => {
    localStorage.setItem('pwa-install-dismissed', 'true');
  }, []);

  // Функция для сброса статуса отклонения промпта
  const resetInstallPrompt = useCallback(() => {
    localStorage.removeItem('pwa-install-dismissed');
  }, []);

  return {
    // Состояние
    isInstalled,
    isOnline,
    isInitialized,
    connectionInfo,
    
    // Функции
    checkSupport,
    getConnectionDetails,
    shouldShowInstallPrompt,
    dismissInstallPrompt,
    resetInstallPrompt
  };
};

export default usePWA;