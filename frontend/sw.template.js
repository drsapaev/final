/**
 * Service Worker для PWA клиники
 * Обеспечивает офлайн работу и кэширование
 *
 * Шаблон для сборки: vite.config.ts подставляет __SW_BUILD_VERSION__
 * (SHA коммита на Vercel / метка времени локальной сборки) и эмитит
 * результат как /sw.js. Каждая сборка получает новую версию кэшей —
 * вернувшиеся пользователи не остаются на старой сборке после деплоя.
 */

/* eslint-disable no-console -- Keep generic service-worker diagnostics without logging request or patient data. */

const BUILD_VERSION = '__SW_BUILD_VERSION__';
const STATIC_CACHE = `clinic-static-${BUILD_VERSION}`;
const DYNAMIC_CACHE = `clinic-dynamic-${BUILD_VERSION}`;
const API_CACHE = `clinic-api-${BUILD_VERSION}`;
const OFFLINE_QUEUE_NAME = 'clinic-offline-queue';
// pwa.ts хранит здесь офлайн-данные приложения — живёт дольше версий сборки.
const PERSISTENT_CACHES = ['clinic-offline-data', OFFLINE_QUEUE_NAME];
const CURRENT_CACHES = [STATIC_CACHE, DYNAMIC_CACHE, API_CACHE, ...PERSISTENT_CACHES];
// If a no-store eviction fails, do not serve any potentially stale entry in
// this worker's lifetime. A healthy storage can be used by the next worker.
let noStoreEvictionFailed = false;

// Файлы для кэширования при установке
const STATIC_FILES = [
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
  // Public-site pages and API reflect current publication state and must
  // never be replayed from Cache Storage, including the offline fallback.
  /^\/$/,
  /^\/ru(?:\/|$)/,
  /^\/(?:services|doctors|prices|contacts)(?:\/|$)/,
  /^\/sitemap\.xml$/,
  /\/api\/v1\/public-site(?:\/|$)/,
  /\/api\/v1\/auth\/login/,
  /\/api\/v1\/auth\/logout/,
  /\/api\/v1\/auth\/me/,
  /\/api\/v1\/payments/,
  /\/api\/v1\/ai/,
  /\/api\/v1\/telegram/,
  /\/api\/v1\/print/
];

// Background Sync задачи
const BACKGROUND_SYNC_TAG = 'clinic-background-sync';

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
            fetch(url).then(async (response) => {
              if (hasNoStore(response.headers)) {
                // Release the unused stream so the remaining precache requests can start.
                // A failed cancellation must not prevent stale-cache eviction.
                await response.body?.cancel().catch(() => undefined);
                try {
                  await deleteCachedRequest(url);
                } catch {
                  noStoreEvictionFailed = true;
                }
              } else if (response.ok) {
                await cache.put(url, response.clone());
              }
            }).catch(() => {
              console.warn('Service Worker: Failed to cache a static file');
              return null;
            })
          )
        );
      })
      .then(() => {
        console.log('Service Worker: Installation complete');
        return self.skipWaiting();
      })
      .catch(() => {
        console.error('Service Worker: Installation failed');
      })
  );
});

// Активация Service Worker: удаляем кэши прошлых сборок
self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activating...');

  event.waitUntil((async () => {
    try {
      const cacheNames = await caches.keys();
      const stale = cacheNames.filter((name) =>
        name.startsWith('clinic-') && !CURRENT_CACHES.includes(name)
      );
      await Promise.all(stale.map((name) => {
        console.log('Service Worker: Deleting an old cache');
        return caches.delete(name);
      }));
    } catch {
      noStoreEvictionFailed = true;
      console.warn('Service Worker: Failed to delete an old cache');
    }

    // Prior workers may have persisted bearer tokens as navigation cache
    // keys, including in caches intentionally retained between builds.
    // Remove only matching entries; preserve unrelated offline clinic data.
    try {
      await purgeSensitiveEntries();
    } catch {
      // Install the fixed worker even if storage is unavailable. Until a
      // later worker can clean it, never replay potentially stale entries.
      noStoreEvictionFailed = true;
      console.warn('Service Worker: Failed to clean sensitive cache entries');
    }

    // Регистрируем background sync если поддерживается
    if ('sync' in self.registration) {
      try {
        await self.registration.sync.register(BACKGROUND_SYNC_TAG);
        console.log('Service Worker: Background sync registered');
      } catch {
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
      } catch {
        console.log('Service Worker: Periodic sync not supported');
      }
    }

    console.log('Service Worker: Activation complete');
    return self.clients.claim();
  })());
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
    // This must precede static-file and HTML routing: a sensitive path can
    // have an extension and previously would reach cacheFirst instead.
    if (isNoCacheRequest(request)) {
      return await networkFirst(
        request, DYNAMIC_CACHE,
        request.mode === 'navigate' || isHtmlRequest(request) ? '/offline.html' : undefined,
      );
    }
    // Навигация: всегда сеть, кэш — только офлайн-фолбэк.
    // Стратегия гарантирует свежий index.html (и свежие хэшированные
    // ассеты) после каждого деплоя.
    if (request.mode === 'navigate' || isHtmlRequest(request)) {
      return await networkFirst(request, DYNAMIC_CACHE, '/offline.html');
    }

    // Стратегия для статических файлов
    if (isStaticFile(url.pathname)) {
      return await cacheFirst(request, STATIC_CACHE);
    }

    // Стратегия для API запросов
    if (isApiRequest(url.pathname)) {
      return await networkFirst(request, DYNAMIC_CACHE);
    }

    // Для остальных запросов - сеть с кэшем
    return await networkFirst(request, DYNAMIC_CACHE);

  } catch {
    console.error('Service Worker: Request failed');

    // Возвращаем офлайн страницу для навигации
    if (request.mode === 'navigate' || isHtmlRequest(request)) {
      const offline = await caches.match('/offline.html');
      if (offline) return offline;
      return new Response('Офлайн режим', { status: 503 });
    }

    // Sensitive and publication-sensitive routes must not replay an older
    // response from Cache Storage after the network-first request failed.
    if (!isNoCacheRequest(request)) {
      const cachedResponse = await caches.match(request);
      if (cachedResponse && !hasNoStore(cachedResponse.headers)) {
        return cachedResponse;
      }
    }

    return new Response('Нет подключения к интернету', { status: 503 });
  }
}

// Cache First стратегия
async function cacheFirst(request, cacheName) {
  try {
    const cachedResponse = await caches.match(request);

    if (cachedResponse && !hasNoStore(cachedResponse.headers)) {
      return cachedResponse;
    }

    const networkResponse = await fetch(request);

    if (hasNoStore(networkResponse.headers)) {
      try {
        await deleteCachedRequest(request);
      } catch {
        noStoreEvictionFailed = true;
        console.warn('Service Worker: Failed to evict an uncached response');
      }
    } else if (networkResponse.ok) {
      try {
        const cache = await caches.open(cacheName);
        await cache.put(request, networkResponse.clone());
      } catch {
        console.warn('Service Worker: Cache write failed');
      }
    }

    return networkResponse;
  } catch (error) {
    console.warn('Service Worker: Cache first failed');
    // Возвращаем кэшированный ответ, если есть
    const cachedResponse = await caches.match(request);
    if (cachedResponse && !hasNoStore(cachedResponse.headers)) {
      return cachedResponse;
    }
    // Иначе возвращаем ошибку
    throw error;
  }
}

// Network First стратегия
async function networkFirst(request, cacheName, offlineFallbackUrl) {
  // Чувствительные маршруты (payments, ai, telegram, print, auth) никогда
  // не попадают в Cache Storage — иначе на общем компьютере клиники
  // офлайн-фолбэк может отдать ответ одного пользователя другому.
  const noCache = isNoCacheRequest(request);
  try {
    const networkResponse = await fetch(request);

    if (hasNoStore(networkResponse.headers)) {
      // Remove an older copy too: a later offline fetch must not replay it.
      try {
        await deleteCachedRequest(request);
      } catch {
        noStoreEvictionFailed = true;
        console.warn('Service Worker: Failed to evict an uncached response');
      }
    } else if (networkResponse.ok && !noCache) {
      try {
        const cache = await caches.open(cacheName);
        await cache.put(request, networkResponse.clone());
      } catch {
        console.warn('Service Worker: Cache write failed');
      }
    }

    return networkResponse;
  } catch (error) {
    console.warn('Service Worker: Network request failed, trying cache');

    const cachedResponse = noCache ? undefined : await caches.match(request);

    if (cachedResponse && !hasNoStore(cachedResponse.headers)) {
      return cachedResponse;
    }

    if (offlineFallbackUrl) {
      const offline = await caches.match(offlineFallbackUrl);
      if (offline) return offline;
    }

    // Если нет кэша, возвращаем ошибку с более информативным сообщением
    console.error('Service Worker: No cache available');
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

// Проверка запрета кэширования (payments, ai, telegram, print, auth)
function isNoCachePath(pathname) {
  const decoded = decodePath(pathname);
  return decoded === null || /(?:^|\/)(?:reset-password|password-reset)(?:\/|$)/i.test(decoded)
    || NO_CACHE_PATTERNS.some(pattern => pattern.test(decoded));
}

function decodePath(pathname) {
  try {
    let decoded = pathname;
    for (let i = 0; i < 3; i += 1) {
      const next = decodeURIComponent(decoded);
      if (next === decoded) return next;
      decoded = next;
    }
    return decoded.includes('%') ? null : decoded;
  } catch {
    return null;
  }
}

function hasNoStore(headers) {
  return /(?:^|,)\s*no-store\s*(?:,|$)/i.test(headers?.get('cache-control') || '');
}

function isSensitiveRequest(request) {
  const url = new URL(typeof request === 'string' ? request : request.url, location.origin);
  if (/(?:^|\/)(?:reset-password|password-reset)(?:\/|$)/i.test(decodePath(url.pathname) || '')) return true;
  // URLSearchParams decodes percent-encoded field names; token-bearing links
  // elsewhere (e.g. older patient invitations) must not become cache keys.
  for (const key of url.searchParams.keys()) {
    try {
      if (decodeURIComponent(key).toLowerCase().includes('token')) return true;
    } catch {
      return true;
    }
  }
  return typeof request !== 'string' && Boolean(request.headers?.get('X-Reset-Token'));
}

function isNoCacheRequest(request) {
  const url = new URL(typeof request === 'string' ? request : request.url, location.origin);
  return noStoreEvictionFailed || isSensitiveRequest(request) || isNoCachePath(url.pathname)
    || (typeof request !== 'string' && (request.cache === 'no-store' || hasNoStore(request.headers)));
}

async function purgeSensitiveEntries() {
  const names = await caches.keys();
  for (const name of names.filter((value) => value.startsWith('clinic-'))) {
    const cache = await caches.open(name);
    for (const request of await cache.keys()) {
      if (isSensitiveRequest(request)) await cache.delete(request);
    }
  }
}

async function deleteCachedRequest(request) {
  const names = await caches.keys();
  for (const name of names.filter((value) => value.startsWith('clinic-'))) {
    const cache = await caches.open(name);
    await cache.delete(request, { ignoreVary: true });
  }
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
      self.clients.openWindow('/')
    );
  } else if (event.action === 'close') {
    // Просто закрываем уведомление
    return;
  } else {
    // По умолчанию открываем главную страницу
    event.waitUntil(
      self.clients.openWindow('/')
    );
  }
});

// Синхронизация в фоне
self.addEventListener('sync', (event) => {
  console.log('Service Worker: Background sync requested');

  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

// Фоновая синхронизация
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

  } catch {
    console.error('Service Worker: Background sync failed');
  }
}

// Обработка сообщений от основного потока
self.addEventListener('message', (event) => {
  console.log('Service Worker: Message received');

  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data && event.data.type === 'CACHE_URLS') {
    event.waitUntil(
      caches.open(DYNAMIC_CACHE)
        .then(async (cache) => {
          for (const url of event.data.urls) {
            if (isNoCacheRequest(url)) continue;
            const response = await fetch(url);
            if (hasNoStore(response.headers)) {
              try {
                await deleteCachedRequest(url);
              } catch {
                noStoreEvictionFailed = true;
              }
            } else if (response.ok) {
              await cache.put(url, response.clone());
            }
          }
        })
    );
  }
});

// Periodic Background Sync (если поддерживается)
self.addEventListener('periodicsync', (event) => {
  console.log('Service Worker: Periodic sync requested');

  if (event.tag === 'clinic-data-sync') {
    event.waitUntil(syncClinicData());
  }
});

// Синхронизация данных клиники
async function syncClinicData() {
  try {
    console.log('Service Worker: Syncing clinic data');

    // Только некритичные для безопасности данные. auth/me не синкаем и
    // не кэшируем: профиль пользователя не должен лежать в Cache Storage
    // на общем компьютере клиники (см. NO_CACHE_PATTERNS).
    const endpoints = [
      '/api/v1/queue/today',
      '/api/v1/mobile/notifications'
    ];

    const cache = await caches.open(API_CACHE);

    for (const endpoint of endpoints) {
      try {
        const response = await fetch(endpoint);
        if (hasNoStore(response.headers)) {
          try {
            await deleteCachedRequest(endpoint);
          } catch {
            noStoreEvictionFailed = true;
          }
        } else if (response.ok) {
          await cache.put(endpoint, response.clone());
          console.log('Service Worker: Synced an endpoint');
        }
      } catch {
        console.log('Service Worker: Failed to sync an endpoint');
      }
    }

  } catch {
    console.error('Service Worker: Clinic data sync failed');
  }
}

// Обработка HEIC конвертации
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CONVERT_HEIC') {
    event.waitUntil(convertHEICToJPEG(event.ports[0]));
  }
});

// HEIC → JPEG конвертация
async function convertHEICToJPEG(port) {
  if (!port) return;

  port.postMessage({
    success: false,
    error: 'HEIC conversion is handled by the app fallback'
  });
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
          console.log('Service Worker: Processed an offline request');
        }
      } catch {
        console.log('Service Worker: Still offline, keeping request in queue');
      }
    }
  } catch {
    console.error('Service Worker: Error processing offline queue');
  }
}

console.log('Service Worker: Loaded with enhanced PWA features');
