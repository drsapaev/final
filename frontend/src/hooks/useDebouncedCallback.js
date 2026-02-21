/**
 * useDebouncedCallback - Хук для дебаунсинга функций
 * 
 * Использует централизованную политику из debouncePolicy.js
 * 
 * @module hooks/useDebouncedCallback
 */

import { useCallback, useRef, useEffect, useState } from 'react';
import { DEBOUNCE } from '../core/debouncePolicy';

/**
 * Создаёт дебаунсированную версию callback-функции
 * 
 * @param {Function} callback - Функция для дебаунсинга
 * @param {number|string} delay - Задержка в мс или ключ из DEBOUNCE policy
 * @param {Array} deps - Зависимости для useCallback
 * 
 * @returns {Function} - Дебаунсированная функция
 * 
 * @example
 * // С числовой задержкой
 * const debouncedSearch = useDebouncedCallback(search, 500, [query]);
 * 
 * // С ключом из policy
 * const debouncedAI = useDebouncedCallback(requestAI, 'ai', [complaints]);
 */
export function useDebouncedCallback(callback, delay, deps = []) {
    const timeoutRef = useRef(null);
    const callbackRef = useRef(callback);

    // Обновляем callback ref при изменении
    useEffect(() => {
        callbackRef.current = callback;
    }, [callback]);

    // Вычисляем реальную задержку
    const resolvedDelay = typeof delay === 'string'
        ? (DEBOUNCE[delay] || DEBOUNCE.search)
        : delay;

    // Очистка при размонтировании
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, []);

    const debouncedCallback = useCallback((...args) => {
        // Отменяем предыдущий таймаут
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }

        // Устанавливаем новый
        timeoutRef.current = setTimeout(() => {
            callbackRef.current(...args);
        }, resolvedDelay);
    }, [resolvedDelay, ...deps]);

    // Метод для немедленного вызова (flush)
    debouncedCallback.flush = useCallback((...args) => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }
        callbackRef.current(...args);
    }, []);

    // Метод для отмены pending вызова
    debouncedCallback.cancel = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }
    }, []);

    return debouncedCallback;
}

/**
 * Хук для дебаунсированного значения
 * 
 * @param {any} value - Значение для дебаунсинга
 * @param {number|string} delay - Задержка
 * 
 * @returns {any} - Дебаунсированное значение
 */
export function useDebouncedValue(value, delay) {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const resolvedDelay = typeof delay === 'string'
            ? (DEBOUNCE[delay] || DEBOUNCE.search)
            : delay;

        const timeout = setTimeout(() => {
            setDebouncedValue(value);
        }, resolvedDelay);

        return () => clearTimeout(timeout);
    }, [value, delay]);

    return debouncedValue;
}

export default useDebouncedCallback;
