/**
 * useVisitLifecycle - Централизованное управление жизненным циклом визита
 * 
 * Критический хук для EMR v2:
 * - Отмена запросов при смене visitId (AbortController)
 * - Инвалидация кэша при смене визита
 * - Сброс состояния компонентов
 * - Предотвращение утечек данных между пациентами
 * 
 * @module hooks/useVisitLifecycle
 */

import { useRef, useEffect, useCallback, useState } from 'react';
import { cacheService } from '../core/cache/cacheService';

/**
 * Hook для управления жизненным циклом визита в EMR
 * 
 * @param {number|string} visitId - ID текущего визита
 * @param {number|string} patientId - ID пациента
 * @param {Object} options - Настройки
 * @param {boolean} options.invalidateCacheOnChange - Очищать кэш при смене визита (default: true)
 * @param {Function} options.onVisitChange - Callback при смене визита
 * @param {Function} options.onCleanup - Callback при очистке
 * 
 * @returns {Object} - API для управления жизненным циклом
 */
export function useVisitLifecycle(visitId, patientId, options = {}) {
    const {
        invalidateCacheOnChange = true,
        onVisitChange,
        onCleanup,
    } = options;

    // AbortController для отмены запросов
    const abortControllerRef = useRef(null);

    // Предыдущие значения для отслеживания изменений
    const prevVisitIdRef = useRef(visitId);
    const prevPatientIdRef = useRef(patientId);

    // Флаг первого рендера
    const isFirstRenderRef = useRef(true);

    // Счётчик активных запросов
    const [activeRequests, setActiveRequests] = useState(0);

    // Флаг очистки
    const [isCleaningUp, setIsCleaningUp] = useState(false);

    /**
     * Создаёт новый AbortController и возвращает signal
     */
    const getAbortSignal = useCallback(() => {
        // Если есть старый контроллер — отменяем его запросы
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        // Создаём новый
        abortControllerRef.current = new AbortController();
        return abortControllerRef.current.signal;
    }, []);

    /**
     * Отменяет все активные запросы
     */
    const abortAllRequests = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
    }, []);

    /**
     * Инвалидирует кэш для текущего визита
     */
    const invalidateVisitCache = useCallback(() => {
        if (cacheService && typeof cacheService.invalidateByVisit === 'function') {
            cacheService.invalidateByVisit(prevVisitIdRef.current);
        }
        if (cacheService && typeof cacheService.invalidateByPatient === 'function') {
            cacheService.invalidateByPatient(prevPatientIdRef.current);
        }
    }, []);

    /**
     * Полная очистка при смене визита
     */
    const performCleanup = useCallback(() => {
        setIsCleaningUp(true);

        // 1. Отменяем все запросы
        abortAllRequests();

        // 2. Инвалидируем кэш
        if (invalidateCacheOnChange) {
            invalidateVisitCache();
        }

        // 3. Вызываем callback очистки
        onCleanup?.();

        setIsCleaningUp(false);
    }, [abortAllRequests, invalidateVisitCache, invalidateCacheOnChange, onCleanup]);

    /**
     * Трекер активных запросов
     */
    const trackRequest = useCallback((promise) => {
        setActiveRequests(prev => prev + 1);

        return promise.finally(() => {
            setActiveRequests(prev => Math.max(0, prev - 1));
        });
    }, []);

    /**
     * Создаёт fetch-обёртку с автоматической отменой
     */
    const createAbortableFetch = useCallback((url, options = {}) => {
        const signal = getAbortSignal();

        return trackRequest(
            fetch(url, { ...options, signal })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    return response.json();
                })
                .catch(error => {
                    if (error.name === 'AbortError') {
                        // Запрос отменён — это нормально
                        return null;
                    }
                    throw error;
                })
        );
    }, [getAbortSignal, trackRequest]);

    // Эффект отслеживания смены visitId
    useEffect(() => {
        // Пропускаем первый рендер
        if (isFirstRenderRef.current) {
            isFirstRenderRef.current = false;
            return;
        }

        // Проверяем, изменился ли visitId или patientId
        const visitChanged = visitId !== prevVisitIdRef.current;
        const patientChanged = patientId !== prevPatientIdRef.current;

        if (visitChanged || patientChanged) {
            // Выполняем очистку
            performCleanup();

            // Уведомляем о смене визита
            onVisitChange?.({
                prevVisitId: prevVisitIdRef.current,
                prevPatientId: prevPatientIdRef.current,
                newVisitId: visitId,
                newPatientId: patientId,
            });

            // Обновляем refs
            prevVisitIdRef.current = visitId;
            prevPatientIdRef.current = patientId;
        }
    }, [visitId, patientId, performCleanup, onVisitChange]);

    // Очистка при размонтировании
    useEffect(() => {
        return () => {
            abortAllRequests();
            if (invalidateCacheOnChange) {
                invalidateVisitCache();
            }
        };
    }, [abortAllRequests, invalidateVisitCache, invalidateCacheOnChange]);

    return {
        // Состояние
        isCleaningUp,
        activeRequests,
        hasActiveRequests: activeRequests > 0,

        // Методы
        getAbortSignal,
        abortAllRequests,
        invalidateVisitCache,
        performCleanup,
        trackRequest,
        createAbortableFetch,

        // Утилиты
        currentVisitId: visitId,
        currentPatientId: patientId,
    };
}

export default useVisitLifecycle;
