/**
 * Debounce Policy - Централизованные настройки дебаунсинга
 * 
 * Единый источник правды для всех debounce-задержек.
 * Изменение UX = изменение одного файла.
 * 
 * @module core/debouncePolicy
 */

/**
 * Константы задержек дебаунсинга (в миллисекундах)
 */
export const DEBOUNCE = {
    /**
     * AI анализ жалоб
     * Высокая задержка — запросы дорогие
     */
    ai: 800,

    /**
     * Текстовый поиск (ICD-10, услуги)
     * Средняя задержка — баланс UX и нагрузки
     */
    search: 500,

    /**
     * История врача / фразы
     * Высокая задержка — данные меняются редко
     */
    history: 2000,

    /**
     * Автосохранение EMR
     * Высокая задержка — не мешать набору текста
     */
    autosave: 3000,

    /**
     * Resize/scroll обработчики
     * Низкая задержка — отзывчивый UI
     */
    ui: 150,

    /**
     * Валидация формы
     * Средняя задержка — показывать ошибки не сразу
     */
    validation: 300,

    /**
     * Телеметрия / логирование
     * Высокая задержка — не критично для UX
     */
    telemetry: 5000,
} as const;

/** Ключи DEBOUNCE — для типизации параметра delay в хуках */
export type DebounceKey = keyof typeof DEBOUNCE;

/**
 * Throttle константы (для scroll/resize)
 */
export const THROTTLE = {
    scroll: 100,
    resize: 200,
    mousemove: 50,
} as const;

export type ThrottleKey = keyof typeof THROTTLE;

export default DEBOUNCE;
