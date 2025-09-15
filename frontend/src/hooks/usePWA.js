import { useState, useEffect, useCallback } from 'react';

/**
 * Hook для работы с PWA функциональностью
 */
export const usePWA = () => {
  const [isInstallable, setIsInstallable] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isServiceWorkerReady, setIsServiceWorkerReady] = useState(false);
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState(null);

  // Проверка установки PWA
  useEffect(() => {
    // Проверяем, запущено ли приложение в standalone режиме
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches ||
                         window.navigator.standalone ||
                         document.referrer.includes('android-app://');
    
    setIsInstalled(isStandalone);
  }, []);

  // Обработка события beforeinstallprompt
  useEffect(() => {
    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setIsInstallable(true);
    };

    const handleAppInstalled = () => {
      setIsInstalled(true);
      setIsInstallable(false);
      setDeferredPrompt(null);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  // Отслеживание онлайн/офлайн статуса
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Регистрация и обновление Service Worker
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js')
        .then((registration) => {
          console.log('Service Worker registered:', registration);
          setIsServiceWorkerReady(true);

          // Проверка обновлений
          registration.addEventListener('updatefound', () => {
            const newWorker = registration.installing;
            
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                setUpdateAvailable(true);
              }
            });
          });
        })
        .catch((error) => {
          console.error('Service Worker registration failed:', error);
        });

      // Слушаем сообщения от Service Worker
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'SYNC_COMPLETE') {
          console.log('Background sync completed');
        }
      });
    }
  }, []);

  // Установка PWA
  const installPWA = useCallback(async () => {
    if (!deferredPrompt) return false;

    try {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      
      if (outcome === 'accepted') {
        console.log('PWA installation accepted');
        setIsInstallable(false);
        setDeferredPrompt(null);
        return true;
      } else {
        console.log('PWA installation declined');
        return false;
      }
    } catch (error) {
      console.error('PWA installation error:', error);
      return false;
    }
  }, [deferredPrompt]);

  // Обновление Service Worker
  const updateServiceWorker = useCallback(() => {
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'SKIP_WAITING' });
      window.location.reload();
    }
  }, []);

  // Запрос разрешения на уведомления
  const requestNotificationPermission = useCallback(async () => {
    if (!('Notification' in window)) {
      return 'not-supported';
    }

    if (Notification.permission === 'granted') {
      return 'granted';
    }

    if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission();
      return permission;
    }

    return 'denied';
  }, []);

  // Отправка push уведомления
  const sendNotification = useCallback(async (title, options = {}) => {
    const permission = await requestNotificationPermission();
    
    if (permission === 'granted') {
      const registration = await navigator.serviceWorker.ready;
      
      await registration.showNotification(title, {
        body: options.body || '',
        icon: options.icon || '/favicon.ico',
        badge: options.badge || '/favicon.ico',
        tag: options.tag || 'clinic-notification',
        requireInteraction: options.requireInteraction || false,
        actions: options.actions || [
          {
            action: 'explore',
            title: 'Открыть',
            icon: '/favicon.ico'
          },
          {
            action: 'close',
            title: 'Закрыть'
          }
        ],
        ...options
      });
      
      return true;
    }
    
    return false;
  }, [requestNotificationPermission]);

  // Кэширование URL в Service Worker
  const cacheUrls = useCallback(async (urls) => {
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({
        type: 'CACHE_URLS',
        urls
      });
    }
  }, []);

  // Проверка поддержки функций
  const capabilities = {
    serviceWorker: 'serviceWorker' in navigator,
    notifications: 'Notification' in window,
    backgroundSync: 'serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype,
    periodicSync: 'serviceWorker' in navigator && 'periodicSync' in window.ServiceWorkerRegistration.prototype,
    webShare: 'share' in navigator,
    clipboard: 'clipboard' in navigator,
    geolocation: 'geolocation' in navigator
  };

  // Функция для проверки, нужно ли показывать промпт установки
  const shouldShowInstallPrompt = useCallback(() => {
    return isInstallable && !isInstalled && deferredPrompt;
  }, [isInstallable, isInstalled, deferredPrompt]);

  return {
    // Состояние
    isInstallable,
    isInstalled,
    isOnline,
    isServiceWorkerReady,
    updateAvailable,
    
    // Методы
    installPWA,
    updateServiceWorker,
    requestNotificationPermission,
    sendNotification,
    cacheUrls,
    shouldShowInstallPrompt,
    
    // Возможности
    capabilities
  };
};

export default usePWA;