/**
 * API кэширование с поддержкой TTL и инвалидации
 */

class APICache {
  constructor() {
    this.cache = new Map();
    this.ttlMap = new Map();
    this.defaultTTL = 5 * 60 * 1000; // 5 минут по умолчанию
    
    // Очистка истекших записей каждую минуту
    setInterval(() => this.cleanup(), 60000);
  }

  /**
   * Генерирует ключ кэша из URL и параметров
   */
  generateKey(url, options = {}) {
    const method = options.method || 'GET';
    const body = options.body ? JSON.stringify(options.body) : '';
    const params = options.params ? new URLSearchParams(options.params).toString() : '';
    
    return `${method}:${url}:${params}:${body}`;
  }

  /**
   * Получает данные из кэша
   */
  get(key) {
    if (!this.cache.has(key)) {
      return null;
    }

    const ttl = this.ttlMap.get(key);
    if (ttl && Date.now() > ttl) {
      this.delete(key);
      return null;
    }

    const data = this.cache.get(key);
    
    // Обновляем время последнего доступа
    if (data) {
      data.lastAccessed = Date.now();
    }
    
    return data;
  }

  /**
   * Сохраняет данные в кэш
   */
  set(key, data, ttl = this.defaultTTL) {
    const cacheEntry = {
      data,
      timestamp: Date.now(),
      lastAccessed: Date.now(),
      size: this.calculateSize(data)
    };

    this.cache.set(key, cacheEntry);
    
    if (ttl > 0) {
      this.ttlMap.set(key, Date.now() + ttl);
    }

    // Проверяем размер кэша
    this.checkCacheSize();
  }

  /**
   * Удаляет запись из кэша
   */
  delete(key) {
    this.cache.delete(key);
    this.ttlMap.delete(key);
  }

  /**
   * Очищает весь кэш
   */
  clear() {
    this.cache.clear();
    this.ttlMap.clear();
  }

  /**
   * Инвалидирует кэш по паттерну
   */
  invalidate(pattern) {
    const regex = new RegExp(pattern);
    
    for (const key of this.cache.keys()) {
      if (regex.test(key)) {
        this.delete(key);
      }
    }
  }

  /**
   * Очищает истекшие записи
   */
  cleanup() {
    const now = Date.now();
    
    for (const [key, ttl] of this.ttlMap.entries()) {
      if (now > ttl) {
        this.delete(key);
      }
    }
  }

  /**
   * Проверяет размер кэша и удаляет старые записи при необходимости
   */
  checkCacheSize() {
    const maxEntries = 1000;
    const maxSize = 50 * 1024 * 1024; // 50MB
    
    if (this.cache.size > maxEntries) {
      this.evictLRU(this.cache.size - maxEntries);
    }

    const totalSize = this.getTotalSize();
    if (totalSize > maxSize) {
      this.evictLRU(Math.ceil(this.cache.size * 0.1)); // Удаляем 10%
    }
  }

  /**
   * Удаляет наименее используемые записи (LRU)
   */
  evictLRU(count) {
    const entries = Array.from(this.cache.entries())
      .sort((a, b) => a[1].lastAccessed - b[1].lastAccessed)
      .slice(0, count);

    for (const [key] of entries) {
      this.delete(key);
    }
  }

  /**
   * Вычисляет размер данных
   */
  calculateSize(data) {
    try {
      return new Blob([JSON.stringify(data)]).size;
    } catch {
      return 1024; // Примерный размер
    }
  }

  /**
   * Получает общий размер кэша
   */
  getTotalSize() {
    let total = 0;
    for (const entry of this.cache.values()) {
      total += entry.size || 0;
    }
    return total;
  }

  /**
   * Получает статистику кэша
   */
  getStats() {
    return {
      entries: this.cache.size,
      totalSize: this.getTotalSize(),
      hitRate: this.hitRate || 0,
      missRate: this.missRate || 0
    };
  }
}

// Глобальный экземпляр кэша
const apiCache = new APICache();

/**
 * Обертка для fetch с кэшированием
 */
export async function cachedFetch(url, options = {}) {
  const {
    cache: cacheOptions = {},
    ...fetchOptions
  } = options;

  const {
    ttl = apiCache.defaultTTL,
    force = false,
    key: customKey
  } = cacheOptions;

  // Генерируем ключ кэша
  const cacheKey = customKey || apiCache.generateKey(url, fetchOptions);

  // Проверяем кэш (если не принудительное обновление)
  if (!force) {
    const cached = apiCache.get(cacheKey);
    if (cached) {
      console.log(`Cache HIT: ${url}`);
      return Promise.resolve(new Response(JSON.stringify(cached.data), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }));
    }
  }

  console.log(`Cache MISS: ${url}`);

  try {
    // Выполняем запрос
    const response = await fetch(url, fetchOptions);
    
    // Кэшируем только успешные GET запросы
    if (response.ok && (fetchOptions.method || 'GET') === 'GET') {
      const data = await response.clone().json();
      apiCache.set(cacheKey, data, ttl);
    }

    return response;
  } catch (error) {
    console.error(`Fetch error for ${url}:`, error);
    throw error;
  }
}

/**
 * Хук для кэшированных API запросов
 */
export function useCachedAPI() {
  return {
    // Получить данные с кэшированием
    get: (url, options = {}) => cachedFetch(url, { ...options, method: 'GET' }),
    
    // Инвалидировать кэш
    invalidate: (pattern) => apiCache.invalidate(pattern),
    
    // Очистить весь кэш
    clear: () => apiCache.clear(),
    
    // Получить статистику
    getStats: () => apiCache.getStats(),
    
    // Предзагрузить данные
    preload: async (url, options = {}) => {
      try {
        await cachedFetch(url, options);
        console.log(`Preloaded: ${url}`);
      } catch (error) {
        console.warn(`Preload failed for ${url}:`, error);
      }
    }
  };
}

/**
 * Стратегии кэширования для разных типов данных
 */
export const CacheStrategies = {
  // Статические данные (справочники)
  STATIC: { ttl: 24 * 60 * 60 * 1000 }, // 24 часа
  
  // Пользовательские данные
  USER: { ttl: 15 * 60 * 1000 }, // 15 минут
  
  // Данные в реальном времени
  REALTIME: { ttl: 30 * 1000 }, // 30 секунд
  
  // Медицинские записи
  MEDICAL: { ttl: 5 * 60 * 1000 }, // 5 минут
  
  // Отчеты и аналитика
  REPORTS: { ttl: 60 * 60 * 1000 }, // 1 час
  
  // Без кэширования
  NO_CACHE: { ttl: 0 }
};

/**
 * Автоматическая инвалидация кэша при изменениях
 */
export function setupCacheInvalidation() {
  // Инвалидация при изменении пользователей
  window.addEventListener('userUpdated', () => {
    apiCache.invalidate('GET:/api/v1/users');
  });

  // Инвалидация при изменении визитов
  window.addEventListener('visitUpdated', () => {
    apiCache.invalidate('GET:/api/v1/visits');
    apiCache.invalidate('GET:/api/v1/queue');
  });

  // Инвалидация при изменении пациентов
  window.addEventListener('patientUpdated', () => {
    apiCache.invalidate('GET:/api/v1/patients');
  });

  // Инвалидация при изменении настроек
  window.addEventListener('settingsUpdated', () => {
    apiCache.invalidate('GET:/api/v1/settings');
  });
}

// Инициализация автоматической инвалидации
if (typeof window !== 'undefined') {
  setupCacheInvalidation();
}

export default apiCache;
