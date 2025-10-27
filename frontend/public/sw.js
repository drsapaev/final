/**
 * Service Worker для PWA клиники
 * Обеспечивает офлайн работу и кэширование
 */

const CACHE_NAME = 'clinic-pwa-v2.0.0';
const STATIC_CACHE = 'clinic-static-v2.0.0';
const DYNAMIC_CACHE = 'clinic-dynamic-v2.0.0';
const API_CACHE = 'clinic-api-v2.0.0';

// Файлы для кэширования при установке
const STATIC_FILES = [
  '/',
  '/manifest.json',
  '/favicon.ico',
  '/offline.html',
  // Основные страницы (только существующие)
  '/login',
  '/dashboard',
  '/patients',
  '/appointments',
  '/queue',
  '/doctor',
  '/registrar',
  '/cashier',
  '/lab',
  '/mobile'
];

// API endpoints для кэширования
const API_CACHE_PATTERNS = [
  /\/api\/v1\/auth\/me/,
  /\/api\/v1\/patients/,
  /\/api\/v1\/visits/,
  /\/api\/v1\/queue/,
  /\/api\/v1\/services/,
  /\/api\/v1\/mobile\/auth\/profile/,
  /\/api\/v1\/mobile\/appointments/,
  /\/api\/v1\/mobile\/stats/,
  /\/api\/v1\/mobile\/notifications/,
  /\/api\/v1\/mobile\/health/
];

// API endpoints которые НЕ нужно кэшировать
const NO_CACHE_PATTERNS = [
  /\/api\/v1\/auth\/login/,
  /\/api\/v1\/auth\/logout/,
  /\/api\/v1\/payments/,
  /\/api\/v1\/ai/,
  /\/api\/v1\/telegram/,
  /\/api\/v1\/print/
];

// Background Sync задачи
const BACKGROUND_SYNC_TAG = 'clinic-background-sync';
const OFFLINE_QUEUE_NAME = 'clinic-offline-queue';

// Установка Service Worker
self.addEventListener('install', (event) => {
  console.log('Service Worker: Installing...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('Service Worker: Caching static files');
        // Кэшируем файлы по одному, чтобы избежать ошибок
        return Promise.allSettled(
          STATIC_FILES.map(url => 
            cache.add(url).catch(err => {
              console.warn(`Service Worker: Failed to cache ${url}:`, err);
              return null;
            })
          )
        );
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
  try {
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
  } catch (error) {
    console.warn('Service Worker: Cache first failed for', request.url, error);
    // Возвращаем кэшированный ответ, если есть
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    // Иначе возвращаем ошибку
    throw error;
  }
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
    console.warn('Service Worker: Network request failed, trying cache:', request.url);
    
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Если нет кэша, возвращаем ошибку с более информативным сообщением
    console.error('Service Worker: No cache available for:', request.url);
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

// Periodic Background Sync (если поддерживается)
self.addEventListener('periodicsync', (event) => {
  console.log('Service Worker: Periodic sync', event.tag);
  
  if (event.tag === 'clinic-data-sync') {
    event.waitUntil(syncClinicData());
  }
});

// Синхронизация данных клиники
async function syncClinicData() {
  try {
    console.log('Service Worker: Syncing clinic data');
    
    // Обновляем критические данные
    const endpoints = [
      '/api/v1/auth/me',
      '/api/v1/queue/today',
      '/api/v1/mobile/notifications'
    ];
    
    const cache = await caches.open(API_CACHE);
    
    for (const endpoint of endpoints) {
      try {
        const response = await fetch(endpoint);
        if (response.ok) {
          await cache.put(endpoint, response.clone());
          console.log(`Service Worker: Synced ${endpoint}`);
        }
      } catch (error) {
        console.log(`Service Worker: Failed to sync ${endpoint}`, error);
      }
    }
    
  } catch (error) {
    console.error('Service Worker: Clinic data sync failed', error);
  }
}

// Обработка HEIC конвертации
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CONVERT_HEIC') {
    event.waitUntil(convertHEICToJPEG(event.data.file, event.ports[0]));
  }
});

// HEIC → JPEG конвертация
async function convertHEICToJPEG(heicFile, port) {
  try {
    // Импортируем heic2any динамически
    const heic2any = (await import('https://cdn.skypack.dev/heic2any')).default;
    
    const jpegBlob = await heic2any({
      blob: heicFile,
      toType: 'image/jpeg',
      quality: 0.8
    });
    
    port.postMessage({
      success: true,
      convertedFile: jpegBlob
    });
    
    console.log('Service Worker: HEIC converted to JPEG');
    
  } catch (error) {
    console.error('Service Worker: HEIC conversion failed', error);
    port.postMessage({
      success: false,
      error: error.message
    });
  }
}

// Обработка офлайн очереди
async function processOfflineQueue() {
  try {
    const cache = await caches.open(OFFLINE_QUEUE_NAME);
    const requests = await cache.keys();
    
    for (const request of requests) {
      try {
        const response = await fetch(request);
        if (response.ok) {
          await cache.delete(request);
          console.log('Service Worker: Processed offline request', request.url);
        }
      } catch (error) {
        console.log('Service Worker: Still offline, keeping request in queue');
      }
    }
  } catch (error) {
    console.error('Service Worker: Error processing offline queue', error);
  }
}

// Обновленная фоновая синхронизация
async function doBackgroundSync() {
  try {
    console.log('Service Worker: Performing background sync');
    
    // Обрабатываем офлайн очередь
    await processOfflineQueue();
    
    // Синхронизируем данные клиники
    await syncClinicData();
    
    // Уведомляем основной поток об успешной синхронизации
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
      client.postMessage({
        type: 'SYNC_COMPLETE',
        timestamp: Date.now()
      });
    });
    
  } catch (error) {
    console.error('Service Worker: Background sync failed', error);
  }
}

// Регистрация Periodic Background Sync при активации
self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activating...');
  
  event.waitUntil((async () => {
    // Очищаем старые кэши
    const cacheNames = await caches.keys();
    const oldCaches = cacheNames.filter(name => 
      name.startsWith('clinic-') && 
      !name.includes('v2.0.0')
    );
    
    await Promise.all(oldCaches.map(name => caches.delete(name)));
    
    // Регистрируем periodic sync если поддерживается
    if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
      try {
        await self.registration.sync.register(BACKGROUND_SYNC_TAG);
        console.log('Service Worker: Background sync registered');
      } catch (error) {
        console.log('Service Worker: Background sync not supported');
      }
    }
    
    // Periodic sync для современных браузеров
    if ('periodicSync' in self.registration) {
      try {
        await self.registration.periodicSync.register('clinic-data-sync', {
          minInterval: 24 * 60 * 60 * 1000, // 24 часа
        });
        console.log('Service Worker: Periodic sync registered');
      } catch (error) {
        console.log('Service Worker: Periodic sync not supported');
      }
    }
    
    return self.clients.claim();
  })());
});

console.log('Service Worker: Loaded successfully with enhanced PWA features');