/**
 * Cache Configuration - Настройки кэширования для EMR v2
 * 
 * Централизованные константы TTL и настройки.
 * Изменение UX = изменение одного файла.
 * 
 * @module core/cache/cacheConfig
 */

export const CACHE_CONFIG = {
    // Default TTL для общих данных (5 минут)
    defaultTTL: 5 * 60 * 1000,

    // TTL для AI-анализа (5 минут)
    // AI-запросы дорогие, но данные быстро устаревают
    aiTTL: 5 * 60 * 1000,

    // TTL для EMR данных (10 минут)
    // EMR меняется редко в рамках одного визита
    emrTTL: 10 * 60 * 1000,

    // TTL для справочников (30 минут)
    // ICD-10, услуги, врачи - меняются редко
    referenceDataTTL: 30 * 60 * 1000,

    // TTL для фраз врача (15 минут)
    doctorPhrasesTTL: 15 * 60 * 1000,

    // Интервал автоочистки (1 минута)
    cleanupInterval: 60 * 1000,

    // Максимальный размер кэша (записей)
    maxSize: 1000,
};

/**
 * Ключи кэша для типизации
 */
export const CACHE_KEYS = {
    AI_ANALYSIS: 'ai:analysis',
    EMR: 'emr',
    ICD10: 'ref:icd10',
    SERVICES: 'ref:services',
    DOCTOR_PHRASES: 'doctor:phrases',
};

/**
 * Теги для групповой инвалидации
 */
export const CACHE_TAGS = {
    visit: (visitId) => `visit:${visitId}`,
    patient: (patientId) => `patient:${patientId}`,
    doctor: (doctorId) => `doctor:${doctorId}`,
    aiAnalysis: 'ai-analysis',
    referenceData: 'reference-data',
};

export default CACHE_CONFIG;
