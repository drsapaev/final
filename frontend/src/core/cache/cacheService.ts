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

interface CacheEntry<T = unknown> {
    value: T;
    expiresAt: number | null;
    tags: string[];
    createdAt: number;
}

interface CacheStats {
    hits: number;
    misses: number;
    sets: number;
    invalidations: number;
}

interface CacheStatsReport extends CacheStats {
    size: number;
    hitRate: number;
}

interface SetOptions {
    ttl?: number;
    tags?: string[];
}

type CacheFactory<T> = () => Promise<T> | T;

class CacheService {
    // Основное хранилище: Map<key, { value, expiresAt, tags }>
    private cache: Map<string, CacheEntry>;

    // Индекс тегов для быстрой инвалидации: Map<tag, Set<key>>
    private tagIndex: Map<string, Set<string>>;

    // Статистика
    private stats: CacheStats;

    constructor() {
        this.cache = new Map<string, CacheEntry>();

        this.tagIndex = new Map<string, Set<string>>();

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
    generateKey(namespace: string, ...parts: Array<string | number | null | undefined>): string {
        return `${namespace}:${parts.filter(Boolean).join(':')}`;
    }

    /**
     * Получает значение из кэша
     *
     * @param key Ключ кэша
     * @returns Значение или null если не найдено/просрочено
     */
    get<T = unknown>(key: string): T | null {
        const entry = this.cache.get(key) as CacheEntry<T> | undefined;

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
     * @param key Ключ кэша
     * @param value Значение
     * @param options Настройки:
     *   - ttl: Time-to-live в миллисекундах
     *   - tags: Теги для групповой инвалидации
     */
    set<T = unknown>(key: string, value: T, options: SetOptions = {}): void {
        const {
            ttl = CACHE_CONFIG.defaultTTL,
            tags = []
        } = options;

        const entry: CacheEntry<T> = {
            value,
            expiresAt: ttl ? Date.now() + ttl : null,
            tags,
            createdAt: Date.now(),
        };

        // Удаляем старую запись из индекса тегов
        this.removeFromTagIndex(key);

        // Сохраняем
        this.cache.set(key, entry as CacheEntry);

        // Обновляем индекс тегов
        tags.forEach(tag => {
            if (!this.tagIndex.has(tag)) {
                this.tagIndex.set(tag, new Set<string>());
            }
            this.tagIndex.get(tag)?.add(key);
        });

        this.stats.sets++;
    }

    /**
     * Удаляет запись из кэша
     */
    delete(key: string): boolean {
        this.removeFromTagIndex(key);
        return this.cache.delete(key);
    }

    /**
     * Удаляет ключ из индекса тегов
     */
    private removeFromTagIndex(key: string): void {
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
    invalidateByTag(tag: string): void {
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
    invalidateByVisit(visitId: string | number | null | undefined): void {
        if (!visitId) return;
        this.invalidateByTag(`visit:${visitId}`);
    }

    /**
     * Инвалидирует кэш по patientId
     */
    invalidateByPatient(patientId: string | number | null | undefined): void {
        if (!patientId) return;
        this.invalidateByTag(`patient:${patientId}`);
    }

    /**
     * Полная очистка кэша
     */
    clear(): void {
        this.cache.clear();
        this.tagIndex.clear();
        this.stats.invalidations++;
    }

    /**
     * Получает или создаёт кэшированное значение
     *
     * @param key Ключ
     * @param factory Функция создания значения
     * @param options Настройки кэширования
     */
    async getOrSet<T = unknown>(key: string, factory: CacheFactory<T>, options: SetOptions = {}): Promise<T> {
        const cached = this.get<T>(key);
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
    cacheAIRequest<T = unknown>(complaintsHash: string, specialty: string, result: T): void {
        const key = this.generateKey('ai', 'analysis', complaintsHash, specialty);
        this.set(key, result, {
            ttl: CACHE_CONFIG.aiTTL,
            tags: ['ai-analysis'],
        });
    }

    /**
     * Получает кэшированный AI-результат
     */
    getAIRequest<T = unknown>(complaintsHash: string, specialty: string): T | null {
        const key = this.generateKey('ai', 'analysis', complaintsHash, specialty);
        return this.get<T>(key);
    }

    /**
     * Кэширует EMR данные
     */
    cacheEMR<T = unknown>(visitId: string | number, emrData: T): void {
        const key = this.generateKey('emr', visitId);
        this.set(key, emrData, {
            ttl: CACHE_CONFIG.emrTTL,
            tags: [`visit:${visitId}`],
        });
    }

    /**
     * Получает кэшированные EMR данные
     */
    getEMR<T = unknown>(visitId: string | number): T | null {
        const key = this.generateKey('emr', visitId);
        return this.get<T>(key);
    }

    /**
     * Автоматическая очистка просроченных записей
     */
    private startAutoCleanup(): void {
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
    getStats(): CacheStatsReport {
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
