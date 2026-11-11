/**
 * useDoctorPhrases - хук для подсказок из истории врача
 * 
 * Принцип: это НЕ генерация текста, а поиск и ранжирование
 * ранее введённых врачом фраз.
 * 
 * АВТОМАТИЧЕСКАЯ АКТИВАЦИЯ: autocomplete включается ТОЛЬКО
 * когда врач накопил достаточно данных (≥10 EMR, ≥30 фраз, ≥5 повторов).
 * 
 * До этого — полностью OFF, без UI switch.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api/client';
import logger from '../utils/logger';
import { formatNetworkErrorMessage } from '../utils/networkErrorMessages';
import { getErrorMessage } from '../utils/type-guards';
import type { AsyncState } from '../types/async-state';
import { idleState, loadingState, successState, errorState, getError } from '../types/async-state';

// Дефолтные настройки
const DEFAULT_CONFIG = {
  debounceMs: 300,
  minQueryLength: 3,
  maxSuggestions: 5
};

// Cache для readiness (чтобы не спамить API)
const readinessCache = new Map();
const READINESS_CACHE_TTL = 60000; // 1 минута

/**
 * Hook for doctor's phrase history suggestions
 * 
 * АВТОМАТИЧЕСКАЯ АКТИВАЦИЯ:
 * - Проверяет readiness при mount
 * - Если not ready — suggestions отключены
 * - Если ready — работает как IDE autocomplete
 */
interface UseDoctorPhrasesOptions {
  doctorId?: string | number;
  field?: string;
  specialty?: string | null;
  currentText?: string;
  cursorPosition?: number;
  config?: Record<string, unknown>;
}

export const useDoctorPhrases = ({
  doctorId,
  field = 'complaints',
  specialty = null,
  currentText = '',
  cursorPosition = 0,
  config = {}
}: UseDoctorPhrasesOptions = {}) => {
  const [suggestions, setSuggestions] = useState<unknown[]>([]);
  const [requestState, setRequestState] = useState<AsyncState<unknown>>(idleState<unknown>());

  const loading = requestState.status === 'loading';
  const error = getError(requestState);

  // 🔥 READINESS STATE (automatic activation)
  const [readiness, setReadiness] = useState<{
    ready: boolean;
    checked: boolean;
    progress: number | null;
    message: string | null;
  }>({
    ready: false,
    checked: false,
    progress: null,
    message: null
  });

  // 🔥 PER-FIELD PAUSE (hybrid control)
  // Доступно ТОЛЬКО после readiness=true
  const [paused, setPaused] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastQueryRef = useRef('');
  // EMRPHRASE-FE-001 (audit 3886 round 27): generation counter — any
  // invalidation (short text, context identity change, pause, not-ready)
  // bumps it so a late in-flight response can never commit stale suggestions.
  const generationRef = useRef(0);

  const { debounceMs, minQueryLength, maxSuggestions } = {
    ...DEFAULT_CONFIG,
    ...config
  };

  // ============================================
  // READINESS CHECK (Automatic Activation)
  // ============================================

  const checkReadiness = useCallback(async () => {
    if (!doctorId) {
      setReadiness({ ready: false, checked: true, progress: null, message: 'No doctor ID' });
      return;
    }

    // Check cache first
    const cacheKey = `readiness_${doctorId}`;
    const cached = readinessCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < READINESS_CACHE_TTL) {
      setReadiness({ ...cached.data, checked: true });
      return;
    }

    try {
      const response = await api.get(`/emr/readiness/${doctorId}`);
      const data = response.data;

      const result = {
        ready: data.ready,
        checked: true,
        progress: data.progress,
        message: data.message
      };

      // Cache the result
      readinessCache.set(cacheKey, {
        data: result,
        timestamp: Date.now()
      });

      setReadiness(result);
    } catch (err: unknown) {
      logger.warn('Failed to check readiness:', err);
      // Если не смогли проверить — отключаем
      setReadiness({ ready: false, checked: true, progress: null, message: 'Check failed' });
    }
  }, [doctorId]);

  // Check readiness on mount
  useEffect(() => {
    checkReadiness();
  }, [checkReadiness]);

  // ============================================
  // SUGGESTIONS (only when ready)
  // ============================================

  // Запрос подсказок с сервера
  const fetchSuggestions = useCallback(async (text: string, cursor: number) => {
    // 🔒 НЕ запрашиваем если NOT READY
    if (!readiness.ready) {
      // EMRPHRASE-FE-001: whatever is in flight is now obsolete
      generationRef.current += 1;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      setSuggestions([]);
      return;
    }

    // 🔒 НЕ запрашиваем если PAUSED (per-field control)
    if (paused) {
      generationRef.current += 1;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      setSuggestions([]);
      return;
    }

    if (!doctorId || !text) {
      generationRef.current += 1;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      setSuggestions([]);
      return;
    }

    // Отменяем предыдущий запрос
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    const generation = ++generationRef.current;

    setRequestState(loadingState<unknown>());

    try {
      const response = await api.post('/emr/phrase-suggest', {
        field,
        currentText: text,
        cursorPosition: cursor,
        doctorId,
        specialty,
        maxSuggestions
      }, {
        signal: abortControllerRef.current.signal
      });

      // EMRPHRASE-FE-001: only the request that still owns the current
      // generation may commit its result.
      if (generationRef.current !== generation) return;

      if (response.data?.suggestions) {
        setSuggestions(response.data.suggestions);
      } else {
        setSuggestions([]);
      }
      setRequestState(successState<unknown>(null));
    } catch (err: unknown) {
      if (generationRef.current !== generation) return;
      if ((err as Error).name !== 'AbortError' && (err as Error).name !== 'CanceledError') {
        const errorMessage = formatNetworkErrorMessage({
          responseDetail: (err as Error & { response?: { data?: Record<string, unknown> } })?.response?.data?.detail,
          responseMessage: (err as Error & { response?: { data?: Record<string, unknown> } })?.response?.data?.message,
          rawMessage: getErrorMessage(err),
          fallbackMessage: 'Не удалось получить подсказки из истории врача',
        });
        logger.warn('[DoctorPhrases] Не удалось получить подсказки из истории врача', {
          error: errorMessage,
          rawMessage: getErrorMessage(err),
        });
        setRequestState(errorState<unknown>(String(errorMessage)));
        setSuggestions([]);
      }
      // For AbortError/CanceledError: leave requestState unchanged. The newer
      // request that triggered this abort owns the loading state; resetting
      // here would clobber it (race condition in the original finally block).
    }
  }, [doctorId, field, specialty, maxSuggestions, readiness.ready, paused]);

  // Дебаунс для запросов
  const debouncedFetch = useCallback((text: string, cursor: number) => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // 🔒 НЕ запрашиваем если NOT READY
    if (!readiness.ready) {
      return;
    }

    // Не запрашиваем если текст слишком короткий
    if (text.length < minQueryLength) {
      // EMRPHRASE-FE-001: dropping below the threshold invalidates the
      // in-flight request — abort it, clear results and reset the query
      // memo so growing back to the same text fetches again.
      generationRef.current += 1;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      setSuggestions([]);
      lastQueryRef.current = '';
      return;
    }

    // Не запрашиваем если текст не изменился
    // EMRPHRASE-FE-001: the memo is keyed by the FULL context
    // (doctor + field + specialty + text) — the same text under a different
    // principal is a NEW authorized query, not a duplicate.
    const queryKey = `${doctorId ?? ''}|${field}|${specialty ?? ''}|${text}`;
    if (queryKey === lastQueryRef.current) {
      return;
    }
    lastQueryRef.current = queryKey;

    debounceRef.current = setTimeout(() => {
      fetchSuggestions(text, cursor);
    }, debounceMs);
  }, [fetchSuggestions, debounceMs, minQueryLength, readiness.ready, doctorId, field, specialty]);

  // Эффект при изменении текста
  useEffect(() => {
    debouncedFetch(currentText, cursorPosition);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [currentText, cursorPosition, debouncedFetch]);

  // EMRPHRASE-FE-001 (audit 3886 round 27): a change of the doctor/field/
  // specialty identity invalidates every in-flight request and every memoized
  // query, and re-runs the current text under the new context.
  useEffect(() => {
    generationRef.current += 1;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    setSuggestions([]);
    setRequestState(idleState<unknown>());
    lastQueryRef.current = '';
    if (doctorId && currentText && currentText.length >= minQueryLength && readiness.ready && !paused) {
      debouncedFetch(currentText, cursorPosition);
    }
    // Identity change only — re-running on text/readiness changes is owned by
    // the text effect above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doctorId, field, specialty]);

  // EMRPHRASE-FE-001: pausing or losing readiness ends the suggestion session
  useEffect(() => {
    if (paused || !readiness.ready) {
      generationRef.current += 1;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      setSuggestions([]);
      // no newer request owns the loading state after this invalidation
      setRequestState(idleState<unknown>());
    }
  }, [paused, readiness.ready]);

  // Очистка при размонтировании
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  // ============================================
  // ACTIONS
  // ============================================

  // Очистить подсказки (при принятии или отклонении)
  const clearSuggestions = useCallback(() => {
    setSuggestions([]);
    lastQueryRef.current = '';
  }, []);

  // Принять подсказку (вернёт полный текст с continuation)
  const acceptSuggestion = useCallback((suggestion: Record<string, unknown>) => {
    if (!suggestion?.text) return currentText;

    // Вставляем хвост после курсора
    const before = currentText.slice(0, cursorPosition);
    const after = currentText.slice(cursorPosition);

    return before + suggestion.text + after;
  }, [currentText, cursorPosition]);

  // Проиндексировать EMR данные (вызывается после сохранения)
  const indexPhrases = useCallback(async (emrData: Record<string, unknown>) => {
    if (!doctorId) return;

    try {
      await api.post('/emr/phrase-index', {
        doctorId,
        specialty,
        emrData
      });

      // Invalidate readiness cache (may have become ready)
      readinessCache.delete(`readiness_${doctorId}`);

      // Re-check readiness
      checkReadiness();
    } catch (err: unknown) {
      logger.warn('Failed to index phrases:', err);
    }
  }, [doctorId, specialty, checkReadiness]);

  // Record telemetry event
  const recordTelemetry = useCallback(async (event: string, phraseId: string | number | null = null, timeMs: number | null = null) => {
    if (!doctorId) return;

    try {
      await api.post('/emr/telemetry', {
        doctorId,
        field,
        event,
        phraseId,
        timeMs
      });
    } catch {

      // Telemetry failures are silent
    }}, [doctorId, field]);

  return {
    // State
    suggestions,
    loading,
    error,

    // 🔥 READINESS (automatic activation)
    ready: readiness.ready,
    readinessChecked: readiness.checked,
    readinessProgress: readiness.progress,
    readinessMessage: readiness.message,

    // 🔥 PER-FIELD PAUSE (hybrid control)
    paused,
    togglePause: () => setPaused((prev) => !prev),

    // Первая подсказка (для ghost text)
    topSuggestion: suggestions[0] || null,

    // Actions
    clearSuggestions,
    acceptSuggestion,
    indexPhrases,
    recordTelemetry,

    // Manual fetch (если нужно принудительно)
    refetch: () => fetchSuggestions(currentText, cursorPosition),
    recheckReadiness: checkReadiness
  };
};

export default useDoctorPhrases;
