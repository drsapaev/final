import { useState, useEffect, useCallback, useRef } from 'react';

const useAdminData = (url, options = {}) => {
  const {
    refreshInterval = 0,
    onError = () => {},
    onSuccess = () => {},
    initialData = null,
    enabled = true
  } = options;

  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);
  const abortControllerRef = useRef(null);
  const mountedRef = useRef(true);

  // Стабильные ссылки на колбэки
  const onErrorRef = useRef(onError);
  const onSuccessRef = useRef(onSuccess);

  // Обновляем ссылки на колбэки
  useEffect(() => {
    onErrorRef.current = onError;
    onSuccessRef.current = onSuccess;
  });

  const fetchData = useCallback(async (signal) => {
    if (!enabled || !url || !mountedRef.current) return;

    try {
      setLoading(true);
      setError(null);

      // Отменяем предыдущий запрос если он есть
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Создаем новый AbortController
      abortControllerRef.current = new AbortController();
      const currentSignal = signal || abortControllerRef.current.signal;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
        },
        signal: currentSignal
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      if (mountedRef.current) {
        setData(result);
        onSuccessRef.current(result);
      }
    } catch (err) {
      if (err.name !== 'AbortError' && mountedRef.current) {
        setError(err);
        onErrorRef.current(err);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [url, enabled]);

  const refresh = useCallback(() => {
    fetchData();
  }, [fetchData]);

  // Первоначальная загрузка
  useEffect(() => {
    if (enabled && url) {
      fetchData();
    }
  }, [enabled, url, fetchData]);

  // Настройка интервала обновления
  useEffect(() => {
    if (refreshInterval > 0 && enabled) {
      intervalRef.current = setInterval(() => {
        fetchData();
      }, refreshInterval);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    }
  }, [refreshInterval, enabled, fetchData]);

  // Очистка при размонтировании
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    data,
    loading,
    error,
    refresh,
    refetch: refresh // Алиас для совместимости
  };
};

export default useAdminData;
