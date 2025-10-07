import { useState, useEffect, useCallback } from 'react';

/**
 * Hook для работы с PWA функциональностью
 * ИСПРАВЛЕНО: Убран избыточный импорт React, добавлены SSR checks
 */
export const usePWA = () => {
  // SSR protection: возвращаем безопасные значения для серверного рендеринга
  const isClient = typeof window !== 'undefined';
  
  if (!isClient) {
    return {
      isInstallable: false,
      isInstalled: false,
      isOnline: true,
      isServiceWorkerReady: false,
      updateAvailable: false,
      installPWA: () => Promise.resolve(false),
      updateServiceWorker: () => {},
      requestNotificationPermission: () => Promise.resolve('not-supported'),
      sendNotification: () => Promise.resolve(false),
      cacheUrls: () => {},
      shouldShowInstallPrompt: () => false,
      capabilities: {}
    };
  }

  // ✅ ИСПРАВЛЕНИЕ: Всегда вызываем хуки первыми
  const [isInstallable, setIsInstallable] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator?.onLine ?? true);
  const [isServiceWorkerReady, setIsServiceWorkerReady] = useState(false);
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState(null);

  // Проверка установки PWA
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    // Проверяем, запущено ли приложение в standalone режиме
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches ||
                         window.navigator.standalone ||
                         document.referrer.includes('android-app://');
    
    setIsInstalled(isStandalone);
  }, []);

  // Обработка события beforeinstallprompt
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
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
    if (typeof window === 'undefined') return;
    
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
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;
    
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
  }, []);

  // Установка PWA
  const installPWA = useCallback(async () => {
    if (typeof window === 'undefined' || !deferredPrompt) return false;

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
    if (typeof window === 'undefined' || !('serviceWorker' in navigator) || !navigator.serviceWorker.controller) return;
    
    navigator.serviceWorker.controller.postMessage({ type: 'SKIP_WAITING' });
    window.location.reload();
  }, []);

  // Запрос разрешения на уведомления
  const requestNotificationPermission = useCallback(async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
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
    if (typeof window === 'undefined' || !('serviceWorker' in navigator) || !navigator.serviceWorker.controller) return;
    
    navigator.serviceWorker.controller.postMessage({
      type: 'CACHE_URLS',
      urls
    });
  }, []);

  // Проверка поддержки функций
  const capabilities = {
    serviceWorker: typeof window !== 'undefined' && 'serviceWorker' in navigator,
    notifications: typeof window !== 'undefined' && 'Notification' in window,
    backgroundSync: typeof window !== 'undefined' && 'serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype,
    periodicSync: typeof window !== 'undefined' && 'serviceWorker' in navigator && 'periodicSync' in window.ServiceWorkerRegistration.prototype,
    webShare: typeof window !== 'undefined' && 'share' in navigator,
    clipboard: typeof window !== 'undefined' && 'clipboard' in navigator,
    geolocation: typeof window !== 'undefined' && 'geolocation' in navigator
  };

  // Функция для проверки, нужно ли показывать промпт установки
  const shouldShowInstallPrompt = useCallback(() => {
    return isInstallable && !isInstalled && deferredPrompt;
  }, [isInstallable, isInstalled, deferredPrompt]);

  return {
    // Состояние
    isInstallable: isClient ? isInstallable : false,
    isInstalled: isClient ? isInstalled : false,
    isOnline: isClient ? isOnline : true,
    isServiceWorkerReady: isClient ? isServiceWorkerReady : false,
    updateAvailable: isClient ? updateAvailable : false,
    
    // Методы
    installPWA: isClient ? installPWA : () => Promise.resolve(false),
    updateServiceWorker: isClient ? updateServiceWorker : () => {},
    requestNotificationPermission: isClient ? requestNotificationPermission : () => Promise.resolve('not-supported'),
    sendNotification: isClient ? sendNotification : () => Promise.resolve(false),
    cacheUrls: isClient ? cacheUrls : () => {},
    shouldShowInstallPrompt: isClient ? shouldShowInstallPrompt : () => false,
    
    // Возможности
    capabilities: isClient ? capabilities : {}
  };
};

export default usePWA;
