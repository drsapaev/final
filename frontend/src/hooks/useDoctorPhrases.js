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
export const useDoctorPhrases = ({
  doctorId,
  field = 'complaints',
  specialty = null,
  currentText = '',
  cursorPosition = 0,
  config = {}
} = {}) => {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // 🔥 READINESS STATE (automatic activation)
  const [readiness, setReadiness] = useState({
    ready: false,
    checked: false,
    progress: null,
    message: null
  });

  // 🔥 PER-FIELD PAUSE (hybrid control)
  // Доступно ТОЛЬКО после readiness=true
  const [paused, setPaused] = useState(false);

  const abortControllerRef = useRef(null);
  const debounceRef = useRef(null);
  const lastQueryRef = useRef('');

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
    } catch (err) {
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
  const fetchSuggestions = useCallback(async (text, cursor) => {
    // 🔒 НЕ запрашиваем если NOT READY
    if (!readiness.ready) {
      setSuggestions([]);
      return;
    }

    // 🔒 НЕ запрашиваем если PAUSED (per-field control)
    if (paused) {
      setSuggestions([]);
      return;
    }

    if (!doctorId || !text) {
      setSuggestions([]);
      return;
    }

    // Отменяем предыдущий запрос
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setLoading(true);
    setError(null);

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

      if (response.data?.suggestions) {
        setSuggestions(response.data.suggestions);
      } else {
        setSuggestions([]);
      }
    } catch (err) {
      if (err.name !== 'AbortError' && err.name !== 'CanceledError') {
        logger.warn('Failed to fetch phrase suggestions:', err);
        setError(err.message);
        setSuggestions([]);
      }
    } finally {
      setLoading(false);
    }
  }, [doctorId, field, specialty, maxSuggestions, readiness.ready, paused]);

  // Дебаунс для запросов
  const debouncedFetch = useCallback((text, cursor) => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // 🔒 НЕ запрашиваем если NOT READY
    if (!readiness.ready) {
      return;
    }

    // Не запрашиваем если текст слишком короткий
    if (text.length < minQueryLength) {
      setSuggestions([]);
      return;
    }

    // Не запрашиваем если текст не изменился
    if (text === lastQueryRef.current) {
      return;
    }
    lastQueryRef.current = text;

    debounceRef.current = setTimeout(() => {
      fetchSuggestions(text, cursor);
    }, debounceMs);
  }, [fetchSuggestions, debounceMs, minQueryLength, readiness.ready]);

  // Эффект при изменении текста
  useEffect(() => {
    debouncedFetch(currentText, cursorPosition);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [currentText, cursorPosition, debouncedFetch]);

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
  const acceptSuggestion = useCallback((suggestion) => {
    if (!suggestion?.text) return currentText;

    // Вставляем хвост после курсора
    const before = currentText.slice(0, cursorPosition);
    const after = currentText.slice(cursorPosition);

    return before + suggestion.text + after;
  }, [currentText, cursorPosition]);

  // Проиндексировать EMR данные (вызывается после сохранения)
  const indexPhrases = useCallback(async (emrData) => {
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
    } catch (err) {
      logger.warn('Failed to index phrases:', err);
    }
  }, [doctorId, specialty, checkReadiness]);

  // Record telemetry event
  const recordTelemetry = useCallback(async (event, phraseId = null, timeMs = null) => {
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
