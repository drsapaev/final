import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api/client';
import axios from 'axios';

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

  const fetchData = useCallback(async () => {
    if (!enabled || !url || !mountedRef.current) return;

    // Создаем новый AbortController для этого конкретного запроса
    const currentAbortController = new AbortController();
    abortControllerRef.current = currentAbortController;

    try {
      setLoading(true);
      setError(null);

      // Убираем префикс /api/v1 если он есть, так как baseURL уже содержит его
      const cleanUrl = url.startsWith('/api/v1') ? url.replace('/api/v1', '') : url;

      const response = await api.get(cleanUrl);

      // Устанавливаем данные - React сам проверит, смонтирован ли компонент
      setData(response.data);
      onSuccessRef.current(response.data);
    } catch (err) {
      // Игнорируем ошибки отмены запроса
      if (err.name === 'AbortError' || err.name === 'CanceledError' || axios.isCancel(err)) {
        return; // Игнорируем ошибку отмены
      }
      
      setError(err);
      onErrorRef.current(err);
    } finally {
      setLoading(false);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, url]);

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
