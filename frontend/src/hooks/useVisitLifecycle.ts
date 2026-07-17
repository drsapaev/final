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

import { useCallback, useEffect, useRef, useState } from 'react';
import { cacheService } from '../core/cache/cacheService';

export interface VisitChangeInfo {
  prevVisitId: string | number;
  prevPatientId: string | number;
  newVisitId: string | number;
  newPatientId: string | number;
}

export interface UseVisitLifecycleOptions {
  invalidateCacheOnChange?: boolean;
  onVisitChange?: (info: VisitChangeInfo) => void;
  onCleanup?: () => void;
}

export interface UseVisitLifecycleReturn {
  isCleaningUp: boolean;
  activeRequests: number;
  hasActiveRequests: boolean;
  getAbortSignal: () => AbortSignal;
  abortAllRequests: () => void;
  invalidateVisitCache: () => void;
  performCleanup: () => void;
  trackRequest: <T>(promise: Promise<T>) => Promise<T>;
  createAbortableFetch: (url: string, options?: RequestInit) => Promise<unknown>;
  currentVisitId: string | number;
  currentPatientId: string | number;
}

/**
 * Hook для управления жизненным циклом визита в EMR
 */
export function useVisitLifecycle(
  visitId: string | number,
  patientId: string | number,
  options: UseVisitLifecycleOptions = {},
): UseVisitLifecycleReturn {
  const {
    invalidateCacheOnChange = true,
    onVisitChange,
    onCleanup,
  } = options;

  const abortControllerRef = useRef<AbortController | null>(null);
  const prevVisitIdRef = useRef<string | number>(visitId);
  const prevPatientIdRef = useRef<string | number>(patientId);
  const isFirstRenderRef = useRef<boolean>(true);
  const [activeRequests, setActiveRequests] = useState<number>(0);
  const [isCleaningUp, setIsCleaningUp] = useState<boolean>(false);

  const onVisitChangeRef = useRef(onVisitChange);
  const onCleanupRef = useRef(onCleanup);

  useEffect(() => {
    onVisitChangeRef.current = onVisitChange;
    onCleanupRef.current = onCleanup;
  });

  const getAbortSignal = useCallback((): AbortSignal => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    return abortControllerRef.current.signal;
  }, []);

  const abortAllRequests = useCallback((): void => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const invalidateVisitCache = useCallback((): void => {
    if (cacheService && typeof cacheService.invalidateByVisit === 'function') {
      cacheService.invalidateByVisit(prevVisitIdRef.current);
    }
    if (cacheService && typeof cacheService.invalidateByPatient === 'function') {
      cacheService.invalidateByPatient(prevPatientIdRef.current);
    }
  }, []);

  const performCleanup = useCallback((): void => {
    setIsCleaningUp(true);
    abortAllRequests();
    if (invalidateCacheOnChange) {
      invalidateVisitCache();
    }
    onCleanupRef.current?.();
    setIsCleaningUp(false);
  }, [abortAllRequests, invalidateVisitCache, invalidateCacheOnChange]);

  const trackRequest = useCallback(<T,>(promise: Promise<T>): Promise<T> => {
    setActiveRequests((prev) => prev + 1);
    return promise.finally(() => {
      setActiveRequests((prev) => Math.max(0, prev - 1));
    });
  }, []);

  const createAbortableFetch = useCallback(
    (url: string, options: RequestInit = {}): Promise<unknown> => {
      const signal = getAbortSignal();
      return trackRequest(
        fetch(url, { ...options, signal })
          .then((response: Response) => {
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
          })
          .catch((error: Error) => {
            if (error.name === 'AbortError') {
              return null;
            }
            throw error;
          }),
      );
    },
    [getAbortSignal, trackRequest],
  );

  useEffect(() => {
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }

    const visitChanged = visitId !== prevVisitIdRef.current;
    const patientChanged = patientId !== prevPatientIdRef.current;

    if (visitChanged || patientChanged) {
      performCleanup();
      onVisitChangeRef.current?.({
        prevVisitId: prevVisitIdRef.current,
        prevPatientId: prevPatientIdRef.current,
        newVisitId: visitId,
        newPatientId: patientId,
      });
      prevVisitIdRef.current = visitId;
      prevPatientIdRef.current = patientId;
    }
  }, [visitId, patientId, performCleanup]);

  useEffect(() => {
    return () => {
      abortAllRequests();
      if (invalidateCacheOnChange) {
        invalidateVisitCache();
      }
    };
  }, [abortAllRequests, invalidateVisitCache, invalidateCacheOnChange]);

  return {
    isCleaningUp,
    activeRequests,
    hasActiveRequests: activeRequests > 0,
    getAbortSignal,
    abortAllRequests,
    invalidateVisitCache,
    performCleanup,
    trackRequest,
    createAbortableFetch,
    currentVisitId: visitId,
    currentPatientId: patientId,
  };
}

export default useVisitLifecycle;
