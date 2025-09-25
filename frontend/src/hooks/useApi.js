/**
 * Универсальные хуки для API интеграции
 * Заменяют прямые fetch запросы унифицированным подходом
 */

import { useState, useEffect, useCallback } from 'react';
import { api, apiRequest } from '../api/client';
import { toast } from 'react-hot-toast';

/**
 * Хук для выполнения API запросов с состоянием загрузки
 */
export function useApiCall() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const execute = useCallback(async (apiCall, options = {}) => {
    const { 
      showError = true, 
      showSuccess = false, 
      successMessage = 'Операция выполнена успешно',
      errorMessage = 'Произошла ошибка'
    } = options;

    setLoading(true);
    setError(null);

    try {
      const result = await apiCall();
      
      if (showSuccess) {
        toast.success(successMessage);
      }
      
      return result;
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || errorMessage;
      setError(errorMsg);
      
      if (showError) {
        toast.error(errorMsg);
      }
      
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { execute, loading, error };
}

/**
 * Хук для загрузки данных с автоматическим повтором
 */
export function useApiData(endpoint, options = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const {
    params = {},
    dependencies = [],
    autoLoad = true,
    fallbackData = null,
    silent = false
  } = options;

  const loadData = useCallback(async (loadOptions = {}) => {
    const { silent: loadSilent = silent } = loadOptions;
    
    if (!loadSilent) {
      setLoading(true);
    }
    setError(null);

    try {
      const result = await apiRequest('GET', endpoint, { params });
      setData(result);
      return result;
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Ошибка загрузки данных';
      setError(errorMsg);
      
      if (fallbackData) {
        setData(fallbackData);
      }
      
      if (!loadSilent) {
        console.error(`API Error (${endpoint}):`, errorMsg);
      }
      
      throw err;
    } finally {
      if (!loadSilent) {
        setLoading(false);
      }
    }
  }, [endpoint, params, fallbackData, silent]);

  useEffect(() => {
    if (autoLoad) {
      loadData();
    }
  }, [loadData, autoLoad, ...dependencies]);

  const refresh = useCallback(() => loadData(), [loadData]);
  const silentRefresh = useCallback(() => loadData({ silent: true }), [loadData]);

  return { data, loading, error, refresh, silentRefresh, loadData };
}

/**
 * Хук для работы с пациентами
 */
export function usePatients(department = null) {
  const endpoint = department ? `/patients?department=${department}&limit=100` : '/patients?limit=100';
  
  return useApiData(endpoint, {
    fallbackData: [],
    dependencies: [department]
  });
}

/**
 * Хук для работы с записями/визитами
 */
export function useAppointments(options = {}) {
  const { department, limit = 50 } = options;
  const params = { limit };
  if (department) params.department = department;

  return useApiData('/registrar/all-appointments', {
    params,
    fallbackData: [],
    dependencies: [department, limit]
  });
}

/**
 * Хук для работы с очередями
 */
export function useQueues(date = null) {
  const params = date ? { date } : {};
  
  return useApiData('/queues', {
    params,
    fallbackData: [],
    dependencies: [date]
  });
}

/**
 * Хук для работы с услугами
 */
export function useServices(specialty = null) {
  const params = specialty ? { specialty } : {};
  
  return useApiData('/services', {
    params,
    fallbackData: [],
    dependencies: [specialty]
  });
}

/**
 * Хук для отправки форм с валидацией
 */
export function useFormSubmit() {
  const { execute, loading, error } = useApiCall();

  const submitForm = useCallback(async (endpoint, formData, options = {}) => {
    const { method = 'POST', validate = null, transform = null } = options;

    // Валидация данных
    if (validate && typeof validate === 'function') {
      const validationError = validate(formData);
      if (validationError) {
        toast.error(validationError);
        throw new Error(validationError);
      }
    }

    // Трансформация данных
    const dataToSend = transform ? transform(formData) : formData;

    return execute(() => apiRequest(method, endpoint, { data: dataToSend }), {
      showSuccess: true,
      successMessage: 'Данные сохранены успешно'
    });
  }, [execute]);

  return { submitForm, loading, error };
}

/**
 * Хук для работы с файлами
 */
export function useFileUpload() {
  const { execute, loading, error } = useApiCall();

  const uploadFile = useCallback(async (file, endpoint = '/files/upload', options = {}) => {
    const formData = new FormData();
    formData.append('file', file);

    // Добавляем дополнительные поля
    Object.entries(options).forEach(([key, value]) => {
      formData.append(key, value);
    });

    return execute(() => api.post(endpoint, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    }), {
      showSuccess: true,
      successMessage: 'Файл загружен успешно'
    });
  }, [execute]);

  return { uploadFile, loading, error };
}

/**
 * Хук для работы с WebSocket соединениями
 */
export function useWebSocket(url, options = {}) {
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);

  const { 
    onMessage = null, 
    onConnect = null, 
    onDisconnect = null,
    autoConnect = true 
  } = options;

  const connect = useCallback(() => {
    if (socket) return;

    const ws = new WebSocket(url);
    
    ws.onopen = () => {
      setConnected(true);
      if (onConnect) onConnect();
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setLastMessage(message);
      if (onMessage) onMessage(message);
    };

    ws.onclose = () => {
      setConnected(false);
      setSocket(null);
      if (onDisconnect) onDisconnect();
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    setSocket(ws);
  }, [url, onMessage, onConnect, onDisconnect, socket]);

  const disconnect = useCallback(() => {
    if (socket) {
      socket.close();
    }
  }, [socket]);

  const sendMessage = useCallback((message) => {
    if (socket && connected) {
      socket.send(JSON.stringify(message));
    }
  }, [socket, connected]);

  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      if (socket) {
        socket.close();
      }
    };
  }, [connect, autoConnect]);

  return { connect, disconnect, sendMessage, connected, lastMessage };
}

/**
 * Хук для кэширования данных
 */
export function useCachedData(key, fetcher, options = {}) {
  const { ttl = 5 * 60 * 1000, fallback = null } = options; // 5 минут по умолчанию
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadCachedData = async () => {
      try {
        // Проверяем кэш
        const cached = localStorage.getItem(`cache_${key}`);
        if (cached) {
          const { data: cachedData, timestamp } = JSON.parse(cached);
          if (Date.now() - timestamp < ttl) {
            setData(cachedData);
            setLoading(false);
            return;
          }
        }

        // Загружаем свежие данные
        const freshData = await fetcher();
        setData(freshData);
        
        // Сохраняем в кэш
        localStorage.setItem(`cache_${key}`, JSON.stringify({
          data: freshData,
          timestamp: Date.now()
        }));
      } catch (error) {
        console.error('Cache error:', error);
        if (fallback) {
          setData(fallback);
        }
      } finally {
        setLoading(false);
      }
    };

    loadCachedData();
  }, [key, fetcher, ttl, fallback]);

  const clearCache = useCallback(() => {
    localStorage.removeItem(`cache_${key}`);
  }, [key]);

  return { data, loading, clearCache };
}
