/**
 * Cache Service - Централизованный сервис кэширования для EMR v2
 * 
 * Features:
 * - Memory cache с TTL
 * - Инвалидация по visitId/patientId
 * - Поддержка AI-запросов
 * - Автоочистка просроченных записей
 * 
 * @module core/cache/cacheService
 */

import { CACHE_CONFIG } from './cacheConfig';

class CacheService {
    constructor() {
        // Основное хранилище: Map<key, { value, expiresAt, tags }>
        this.cache = new Map();

        // Индекс тегов для быстрой инвалидации: Map<tag, Set<key>>
        this.tagIndex = new Map();

        // Статистика
        this.stats = {
            hits: 0,
            misses: 0,
            sets: 0,
            invalidations: 0,
        };

        // Запуск автоочистки
        this.startAutoCleanup();
    }

    /**
     * Генерирует ключ кэша
     */
    generateKey(namespace, ...parts) {
        return `${namespace}:${parts.filter(Boolean).join(':')}`;
    }

    /**
     * Получает значение из кэша
     * 
     * @param {string} key - Ключ кэша
     * @returns {any|null} - Значение или null если не найдено/просрочено
     */
    get(key) {
        const entry = this.cache.get(key);

        if (!entry) {
            this.stats.misses++;
            return null;
        }

        // Проверяем TTL
        if (entry.expiresAt && Date.now() > entry.expiresAt) {
            this.delete(key);
            this.stats.misses++;
            return null;
        }

        this.stats.hits++;
        return entry.value;
    }

    /**
     * Сохраняет значение в кэш
     * 
     * @param {string} key - Ключ кэша
     * @param {any} value - Значение
     * @param {Object} options - Настройки
     * @param {number} options.ttl - Time-to-live в миллисекундах
     * @param {string[]} options.tags - Теги для групповой инвалидации
     */
    set(key, value, options = {}) {
        const {
            ttl = CACHE_CONFIG.defaultTTL,
            tags = []
        } = options;

        const entry = {
            value,
            expiresAt: ttl ? Date.now() + ttl : null,
            tags,
            createdAt: Date.now(),
        };

        // Удаляем старую запись из индекса тегов
        this.removeFromTagIndex(key);

        // Сохраняем
        this.cache.set(key, entry);

        // Обновляем индекс тегов
        tags.forEach(tag => {
            if (!this.tagIndex.has(tag)) {
                this.tagIndex.set(tag, new Set());
            }
            this.tagIndex.get(tag).add(key);
        });

        this.stats.sets++;
    }

    /**
     * Удаляет запись из кэша
     */
    delete(key) {
        this.removeFromTagIndex(key);
        return this.cache.delete(key);
    }

    /**
     * Удаляет ключ из индекса тегов
     */
    removeFromTagIndex(key) {
        const entry = this.cache.get(key);
        if (entry?.tags) {
            entry.tags.forEach(tag => {
                const tagKeys = this.tagIndex.get(tag);
                if (tagKeys) {
                    tagKeys.delete(key);
                    if (tagKeys.size === 0) {
                        this.tagIndex.delete(tag);
                    }
                }
            });
        }
    }

    /**
     * Инвалидирует все записи с указанным тегом
     */
    invalidateByTag(tag) {
        const keys = this.tagIndex.get(tag);
        if (keys) {
            keys.forEach(key => this.cache.delete(key));
            this.tagIndex.delete(tag);
            this.stats.invalidations++;
        }
    }

    /**
     * Инвалидирует кэш по visitId
     */
    invalidateByVisit(visitId) {
        if (!visitId) return;
        this.invalidateByTag(`visit:${visitId}`);
    }

    /**
     * Инвалидирует кэш по patientId
     */
    invalidateByPatient(patientId) {
        if (!patientId) return;
        this.invalidateByTag(`patient:${patientId}`);
    }

    /**
     * Полная очистка кэша
     */
    clear() {
        this.cache.clear();
        this.tagIndex.clear();
        this.stats.invalidations++;
    }

    /**
     * Получает или создаёт кэшированное значение
     * 
     * @param {string} key - Ключ
     * @param {Function} factory - Функция создания значения
     * @param {Object} options - Настройки кэширования
     */
    async getOrSet(key, factory, options = {}) {
        const cached = this.get(key);
        if (cached !== null) {
            return cached;
        }

        const value = await factory();
        this.set(key, value, options);
        return value;
    }

    /**
     * Кэширует AI-запрос
     */
    cacheAIRequest(complaintsHash, specialty, result) {
        const key = this.generateKey('ai', 'analysis', complaintsHash, specialty);
        this.set(key, result, {
            ttl: CACHE_CONFIG.aiTTL,
            tags: ['ai-analysis'],
        });
    }

    /**
     * Получает кэшированный AI-результат
     */
    getAIRequest(complaintsHash, specialty) {
        const key = this.generateKey('ai', 'analysis', complaintsHash, specialty);
        return this.get(key);
    }

    /**
     * Кэширует EMR данные
     */
    cacheEMR(visitId, emrData) {
        const key = this.generateKey('emr', visitId);
        this.set(key, emrData, {
            ttl: CACHE_CONFIG.emrTTL,
            tags: [`visit:${visitId}`],
        });
    }

    /**
     * Получает кэшированные EMR данные
     */
    getEMR(visitId) {
        const key = this.generateKey('emr', visitId);
        return this.get(key);
    }

    /**
     * Автоматическая очистка просроченных записей
     */
    startAutoCleanup() {
        setInterval(() => {
            const now = Date.now();
            for (const [key, entry] of this.cache.entries()) {
                if (entry.expiresAt && now > entry.expiresAt) {
                    this.delete(key);
                }
            }
        }, CACHE_CONFIG.cleanupInterval);
    }

    /**
     * Возвращает статистику кэша
     */
    getStats() {
        return {
            ...this.stats,
            size: this.cache.size,
            hitRate: this.stats.hits / (this.stats.hits + this.stats.misses) || 0,
        };
    }
}

// Singleton instance
export const cacheService = new CacheService();

export default cacheService;
