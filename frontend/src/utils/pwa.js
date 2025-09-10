/**
 * PWA утилиты для регистрации Service Worker и управления PWA функциями
 */

// Регистрация Service Worker
export async function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/'
      });
      
      console.log('Service Worker зарегистрирован:', registration);
      
      // Обработка обновлений
      registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed') {
            if (navigator.serviceWorker.controller) {
              // Новый контент доступен
              showUpdateNotification();
            } else {
              // Контент кэширован для офлайн использования
              console.log('PWA готов к офлайн использованию');
            }
          }
        });
      });
      
      return registration;
    } catch (error) {
      console.error('Ошибка регистрации Service Worker:', error);
      return null;
    }
  } else {
    console.log('Service Worker не поддерживается');
    return null;
  }
}

// Показ уведомления об обновлении
function showUpdateNotification() {
  if (confirm('Доступна новая версия приложения. Обновить?')) {
    window.location.reload();
  }
}

// Проверка поддержки PWA функций
export function checkPWASupport() {
  const support = {
    serviceWorker: 'serviceWorker' in navigator,
    pushManager: 'PushManager' in window,
    notification: 'Notification' in window,
    backgroundSync: 'serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype,
    cache: 'caches' in window,
    indexedDB: 'indexedDB' in window
  };
  
  console.log('PWA поддержка:', support);
  return support;
}

// Запрос разрешения на уведомления
export async function requestNotificationPermission() {
  if ('Notification' in window) {
    const permission = await Notification.requestPermission();
    
    if (permission === 'granted') {
      console.log('Разрешение на уведомления получено');
      return true;
    } else {
      console.log('Разрешение на уведомления отклонено');
      return false;
    }
  }
  
  return false;
}

// Подписка на push уведомления
export async function subscribeToPushNotifications() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    console.log('Push уведомления не поддерживаются');
    return null;
  }
  
  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: process.env.REACT_APP_VAPID_PUBLIC_KEY
    });
    
    console.log('Подписка на push уведомления создана:', subscription);
    
    // Отправляем подписку на сервер
    await sendSubscriptionToServer(subscription);
    
    return subscription;
  } catch (error) {
    console.error('Ошибка подписки на push уведомления:', error);
    return null;
  }
}

// Отправка подписки на сервер
async function sendSubscriptionToServer(subscription) {
  try {
    const response = await fetch('/api/v1/mobile/notifications/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
      },
      body: JSON.stringify(subscription)
    });
    
    if (response.ok) {
      console.log('Подписка отправлена на сервер');
    } else {
      console.error('Ошибка отправки подписки на сервер');
    }
  } catch (error) {
    console.error('Ошибка отправки подписки:', error);
  }
}

// Установка PWA
export function installPWA() {
  // Проверяем, можно ли установить PWA
  if (window.deferredPrompt) {
    window.deferredPrompt.prompt();
    
    window.deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        console.log('PWA установлено');
      } else {
        console.log('PWA не установлено');
      }
      window.deferredPrompt = null;
    });
  }
}

// Проверка, установлено ли PWA
export function isPWAInstalled() {
  return window.matchMedia('(display-mode: standalone)').matches ||
         window.navigator.standalone === true;
}

// Получение информации о подключении
export function getConnectionInfo() {
  if ('connection' in navigator) {
    return {
      effectiveType: navigator.connection.effectiveType,
      downlink: navigator.connection.downlink,
      rtt: navigator.connection.rtt,
      saveData: navigator.connection.saveData
    };
  }
  
  return null;
}

// Обработка офлайн/онлайн событий
export function setupConnectionHandlers() {
  window.addEventListener('online', () => {
    console.log('Подключение восстановлено');
    // Можно показать уведомление или синхронизировать данные
    showConnectionNotification('online');
  });
  
  window.addEventListener('offline', () => {
    console.log('Подключение потеряно');
    showConnectionNotification('offline');
  });
}

// Показ уведомления о статусе подключения
function showConnectionNotification(status) {
  // Создаем простое уведомление
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 20px;
    border-radius: 8px;
    color: white;
    font-weight: 500;
    z-index: 10000;
    transition: all 0.3s ease;
    ${status === 'online' 
      ? 'background: #10b981;' 
      : 'background: #ef4444;'
    }
  `;
  
  notification.textContent = status === 'online' 
    ? '🟢 Подключение восстановлено' 
    : '🔴 Нет подключения к интернету';
  
  document.body.appendChild(notification);
  
  // Убираем уведомление через 3 секунды
  setTimeout(() => {
    notification.style.opacity = '0';
    setTimeout(() => {
      document.body.removeChild(notification);
    }, 300);
  }, 3000);
}

// Кэширование данных для офлайн работы
export async function cacheDataForOffline(key, data) {
  if ('caches' in window) {
    try {
      const cache = await caches.open('clinic-offline-data');
      await cache.put(`/offline-data/${key}`, new Response(JSON.stringify(data)));
      console.log(`Данные кэшированы для офлайн: ${key}`);
    } catch (error) {
      console.error('Ошибка кэширования данных:', error);
    }
  }
}

// Получение кэшированных данных
export async function getCachedData(key) {
  if ('caches' in window) {
    try {
      const cache = await caches.open('clinic-offline-data');
      const response = await cache.match(`/offline-data/${key}`);
      
      if (response) {
        return await response.json();
      }
    } catch (error) {
      console.error('Ошибка получения кэшированных данных:', error);
    }
  }
  
  return null;
}

// Инициализация PWA
export async function initializePWA() {
  console.log('Инициализация PWA...');
  
  // Проверяем поддержку
  const support = checkPWASupport();
  
  if (!support.serviceWorker) {
    console.log('PWA не поддерживается в этом браузере');
    return;
  }
  
  // Регистрируем Service Worker
  await registerServiceWorker();
  
  // Настраиваем обработчики подключения
  setupConnectionHandlers();
  
  // Запрашиваем разрешение на уведомления
  if (support.notification) {
    await requestNotificationPermission();
  }
  
  console.log('PWA инициализирован');
}

// Экспорт по умолчанию
export default {
  registerServiceWorker,
  checkPWASupport,
  requestNotificationPermission,
  subscribeToPushNotifications,
  installPWA,
  isPWAInstalled,
  getConnectionInfo,
  setupConnectionHandlers,
  cacheDataForOffline,
  getCachedData,
  initializePWA
};
