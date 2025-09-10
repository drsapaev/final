/**
 * Service Worker для PWA клиники
 * Обеспечивает офлайн работу и кэширование
 */

const CACHE_NAME = 'clinic-pwa-v1.0.0';
const STATIC_CACHE = 'clinic-static-v1.0.0';
const DYNAMIC_CACHE = 'clinic-dynamic-v1.0.0';

// Файлы для кэширования при установке
const STATIC_FILES = [
  '/',
  '/index.html',
  '/static/js/bundle.js',
  '/static/css/main.css',
  '/manifest.json',
  '/favicon.ico',
  // Добавляем основные страницы
  '/dashboard',
  '/patients',
  '/appointments',
  '/queue'
];

// API endpoints для кэширования
const API_CACHE_PATTERNS = [
  /\/api\/v1\/mobile\/auth\/profile/,
  /\/api\/v1\/mobile\/appointments/,
  /\/api\/v1\/mobile\/stats/,
  /\/api\/v1\/mobile\/notifications/,
  /\/api\/v1\/mobile\/health/
];

// Установка Service Worker
self.addEventListener('install', (event) => {
  console.log('Service Worker: Installing...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('Service Worker: Caching static files');
        return cache.addAll(STATIC_FILES);
      })
      .then(() => {
        console.log('Service Worker: Installation complete');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('Service Worker: Installation failed', error);
      })
  );
});

// Активация Service Worker
self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activating...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('Service Worker: Deleting old cache', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('Service Worker: Activation complete');
        return self.clients.claim();
      })
  );
});

// Перехват запросов
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Пропускаем не-GET запросы
  if (request.method !== 'GET') {
    return;
  }
  
  // Пропускаем запросы к внешним доменам
  if (url.origin !== location.origin) {
    return;
  }
  
  event.respondWith(
    handleRequest(request)
  );
});

// Обработка запросов
async function handleRequest(request) {
  const url = new URL(request.url);
  
  try {
    // Стратегия для статических файлов
    if (isStaticFile(url.pathname)) {
      return await cacheFirst(request, STATIC_CACHE);
    }
    
    // Стратегия для API запросов
    if (isApiRequest(url.pathname)) {
      return await networkFirst(request, DYNAMIC_CACHE);
    }
    
    // Стратегия для HTML страниц
    if (isHtmlRequest(request)) {
      return await networkFirst(request, DYNAMIC_CACHE);
    }
    
    // Для остальных запросов - сеть с кэшем
    return await networkFirst(request, DYNAMIC_CACHE);
    
  } catch (error) {
    console.error('Service Worker: Request failed', error);
    
    // Возвращаем офлайн страницу для навигации
    if (isHtmlRequest(request)) {
      return await caches.match('/offline.html') || 
             new Response('Офлайн режим', { status: 503 });
    }
    
    // Для API запросов возвращаем кэшированный ответ
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    return new Response('Нет подключения к интернету', { status: 503 });
  }
}

// Cache First стратегия
async function cacheFirst(request, cacheName) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    return cachedResponse;
  }
  
  const networkResponse = await fetch(request);
  
  if (networkResponse.ok) {
    const cache = await caches.open(cacheName);
    cache.put(request, networkResponse.clone());
  }
  
  return networkResponse;
}

// Network First стратегия
async function networkFirst(request, cacheName) {
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    throw error;
  }
}

// Проверка статических файлов
function isStaticFile(pathname) {
  return pathname.match(/\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$/);
}

// Проверка API запросов
function isApiRequest(pathname) {
  return pathname.startsWith('/api/') || API_CACHE_PATTERNS.some(pattern => pattern.test(pathname));
}

// Проверка HTML запросов
function isHtmlRequest(request) {
  return request.headers.get('accept')?.includes('text/html');
}

// Обработка push уведомлений
self.addEventListener('push', (event) => {
  console.log('Service Worker: Push notification received');
  
  const options = {
    body: 'У вас новое уведомление от клиники',
    icon: '/icon-192x192.png',
    badge: '/badge-72x72.png',
    vibrate: [200, 100, 200],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'Открыть',
        icon: '/icon-192x192.png'
      },
      {
        action: 'close',
        title: 'Закрыть',
        icon: '/icon-192x192.png'
      }
    ]
  };
  
  if (event.data) {
    const data = event.data.json();
    options.body = data.body || options.body;
    options.title = data.title || 'Клиника';
  }
  
  event.waitUntil(
    self.registration.showNotification('Клиника', options)
  );
});

// Обработка кликов по уведомлениям
self.addEventListener('notificationclick', (event) => {
  console.log('Service Worker: Notification clicked');
  
  event.notification.close();
  
  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/')
    );
  } else if (event.action === 'close') {
    // Просто закрываем уведомление
    return;
  } else {
    // По умолчанию открываем главную страницу
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

// Синхронизация в фоне
self.addEventListener('sync', (event) => {
  console.log('Service Worker: Background sync', event.tag);
  
  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

// Фоновая синхронизация
async function doBackgroundSync() {
  try {
    // Синхронизируем отложенные данные
    console.log('Service Worker: Performing background sync');
    
    // Здесь можно добавить логику синхронизации
    // например, отправка отложенных форм, обновление данных
    
  } catch (error) {
    console.error('Service Worker: Background sync failed', error);
  }
}

// Обработка сообщений от основного потока
self.addEventListener('message', (event) => {
  console.log('Service Worker: Message received', event.data);
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CACHE_URLS') {
    event.waitUntil(
      caches.open(DYNAMIC_CACHE)
        .then((cache) => {
          return cache.addAll(event.data.urls);
        })
    );
  }
});

console.log('Service Worker: Loaded successfully');