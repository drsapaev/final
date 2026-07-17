/**
 * Универсальные хуки для API интеграции.
 * Заменяют прямые fetch запросы унифицированным подходом.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, apiRequest } from '../api/client';
import { toast } from 'react-toastify';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

// ============================================================================
// useApiCall
// ============================================================================

interface ApiCallOptions {
  showError?: boolean;
  showSuccess?: boolean;
  successMessage?: string;
  errorMessage?: string;
}

interface UseApiCallReturn {
  execute: <T = unknown>(apiCall: () => Promise<T>, options?: ApiCallOptions) => Promise<T>;
  loading: boolean;
  error: string | null;
}

interface CatchError {
  response?: { data?: { detail?: string } };
  message?: string;
}

export function useApiCall(): UseApiCallReturn {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(
    async <T = unknown,>(
      apiCall: () => Promise<T>,
      options: ApiCallOptions = {},
    ): Promise<T> => {
      const {
        showError = true,
        showSuccess = false,
        successMessage = 'Операция выполнена успешно',
        errorMessage = 'Произошла ошибка',
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
        const e = err as CatchError;
        const errorMsg = e?.response?.data?.detail || e?.message || errorMessage;
        setError(String(errorMsg));

        if (showError) {
          toast.error(String(errorMsg));
        }

        throw err;
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { execute, loading, error };
}

// ============================================================================
// useApiData
// ============================================================================

interface UseApiDataOptions {
  params?: Record<string, unknown>;
  dependencies?: unknown[];
  autoLoad?: boolean;
  fallbackData?: unknown;
  silent?: boolean;
}

interface UseApiDataReturn {
  data: unknown;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<unknown>;
  silentRefresh: () => Promise<unknown>;
  loadData: (loadOptions?: { silent?: boolean }) => Promise<unknown>;
}

export function useApiData(
  endpoint: string,
  options: UseApiDataOptions = {},
): UseApiDataReturn {
  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const {
    params = {},
    dependencies = [],
    autoLoad = true,
    fallbackData = null,
    silent = false,
  } = options;

  const loadData = useCallback(
    async (loadOptions: { silent?: boolean } = {}): Promise<unknown> => {
      const { silent: loadSilent = silent } = loadOptions;

      if (!loadSilent) {
        setLoading(true);
      }
      setError(null);

      try {
        const result = await apiRequest<unknown>('GET', endpoint, { params });
        setData(result);
        return result;
      } catch (err) {
        const e = err as CatchError;
        const errorMsg = e?.response?.data?.detail || e?.message || 'Ошибка загрузки данных';
        setError(String(errorMsg));

        if (fallbackData) {
          setData(fallbackData);
        }

        if (!loadSilent) {
          logger.error(`API Error (${endpoint}):`, errorMsg);
        }

        throw err;
      } finally {
        if (!loadSilent) {
          setLoading(false);
        }
      }
    },
    [endpoint, params, fallbackData, silent],
  );

  const dependenciesKey = useMemo(
    () => JSON.stringify(dependencies ?? []),
    [dependencies],
  );

  useEffect(() => {
    if (autoLoad) {
      loadData();
    }
  }, [loadData, autoLoad, dependenciesKey]);

  const refresh = useCallback((): Promise<unknown> => loadData(), [loadData]);
  const silentRefresh = useCallback((): Promise<unknown> => loadData({ silent: true }), [loadData]);

  return { data, loading, error, refresh, silentRefresh, loadData };
}

// ============================================================================
// Domain-specific hooks
// ============================================================================

export function usePatients(department: string | null = null) {
  const endpoint = department
    ? `/patients?department=${department}&limit=100`
    : '/patients?limit=100';

  return useApiData(endpoint, {
    fallbackData: [],
    dependencies: [department],
  });
}

interface UseAppointmentsOptions {
  department?: string | null;
  limit?: number;
}

export function useAppointments(options: UseAppointmentsOptions = {}) {
  const { department, limit = 50 } = options;
  const params: Record<string, unknown> = { limit };
  if (department) params.department = department;

  return useApiData('/registrar/all-appointments', {
    params,
    fallbackData: [],
    dependencies: [department, limit],
  });
}

export function useQueues(date: string | null = null) {
  const params: Record<string, unknown> = date ? { date } : {};

  return useApiData('/queues', {
    params,
    fallbackData: [],
    dependencies: [date],
  });
}

export function useServices(specialty: string | null = null) {
  const params: Record<string, unknown> = specialty ? { specialty } : {};

  return useApiData('/services', {
    params,
    fallbackData: [],
    dependencies: [specialty],
  });
}

// ============================================================================
// useFormSubmit
// ============================================================================

interface FormSubmitOptions {
  method?: string;
  validate?: ((data: Record<string, unknown>) => string | null) | null;
  transform?: ((data: Record<string, unknown>) => Record<string, unknown>) | null;
}

interface UseFormSubmitReturn {
  submitForm: (
    endpoint: string,
    formData: Record<string, unknown>,
    options?: FormSubmitOptions,
  ) => Promise<unknown>;
  loading: boolean;
  error: string | null;
}

export function useFormSubmit(): UseFormSubmitReturn {
  const { execute, loading, error } = useApiCall();

  const submitForm = useCallback(
    async (
      endpoint: string,
      formData: Record<string, unknown>,
      options: FormSubmitOptions = {},
    ): Promise<unknown> => {
      const { method = 'POST', validate = null, transform = null } = options;

      if (validate && typeof validate === 'function') {
        const validationError = validate(formData);
        if (validationError) {
          toast.error(validationError);
          throw new Error(validationError);
        }
      }

      const dataToSend = transform ? transform(formData) : formData;

      return execute(
        () => apiRequest<unknown>(method, endpoint, { data: dataToSend }),
        {
          showSuccess: true,
          successMessage: 'Данные сохранены успешно',
        },
      );
    },
    [execute],
  );

  return { submitForm, loading, error };
}

// ============================================================================
// useFileUpload
// ============================================================================

interface UseFileUploadReturn {
  uploadFile: (
    file: File | Blob,
    endpoint?: string,
    options?: Record<string, unknown>,
  ) => Promise<unknown>;
  loading: boolean;
  error: string | null;
}

export function useFileUpload(): UseFileUploadReturn {
  const { execute, loading, error } = useApiCall();

  const uploadFile = useCallback(
    async (
      file: File | Blob,
      endpoint: string = '/files/upload',
      options: Record<string, unknown> = {},
    ): Promise<unknown> => {
      const formData = new FormData();
      formData.append('file', file);

      Object.entries(options).forEach(([key, value]) => {
        formData.append(key, String(value));
      });

      return execute(
        () =>
          api.post(endpoint, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
          }),
        {
          showSuccess: true,
          successMessage: 'Файл загружен успешно',
        },
      );
    },
    [execute],
  );

  return { uploadFile, loading, error };
}

// ============================================================================
// useWebSocket
// ============================================================================

interface UseWebSocketOptions {
  onMessage?: ((message: unknown) => void) | null;
  onConnect?: (() => void) | null;
  onDisconnect?: (() => void) | null;
  autoConnect?: boolean;
}

interface UseWebSocketReturn {
  connect: () => void;
  disconnect: () => void;
  sendMessage: (message: unknown) => void;
  connected: boolean;
  lastMessage: unknown;
}

export function useWebSocket(
  url: string,
  options: UseWebSocketOptions = {},
): UseWebSocketReturn {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState<boolean>(false);
  const [lastMessage, setLastMessage] = useState<unknown>(null);

  const {
    onMessage = null,
    onConnect = null,
    onDisconnect = null,
    autoConnect = true,
  } = options;

  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onConnectRef.current = onConnect;
    onDisconnectRef.current = onDisconnect;
  });

  const connect = useCallback((): void => {
    if (socket) return;

    const token = tokenManager.getAccessToken();
    const subprotocols = token ? [`bearer.${token}`] : [];

    const ws = new WebSocket(url, subprotocols);

    ws.onopen = (): void => {
      setConnected(true);
      onConnectRef.current?.();
    };

    ws.onmessage = (event: MessageEvent): void => {
      const message: unknown = JSON.parse(event.data);
      setLastMessage(message);
      onMessageRef.current?.(message);
    };

    ws.onclose = (): void => {
      setConnected(false);
      setSocket(null);
      onDisconnectRef.current?.();
    };

    ws.onerror = (error: Event): void => {
      logger.error('WebSocket error:', error);
    };

    setSocket(ws);
  }, [url, socket]);

  const disconnect = useCallback((): void => {
    if (socket) {
      socket.close();
    }
  }, [socket]);

  const sendMessage = useCallback(
    (message: unknown): void => {
      if (socket && connected) {
        socket.send(JSON.stringify(message));
      }
    },
    [socket, connected],
  );

  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [connect, autoConnect, disconnect]);

  return { connect, disconnect, sendMessage, connected, lastMessage };
}

// ============================================================================
// useCachedData
// ============================================================================

interface UseCachedDataOptions {
  ttl?: number;
  fallback?: unknown;
}

interface UseCachedDataReturn {
  data: unknown;
  loading: boolean;
  clearCache: () => void;
}

export function useCachedData(
  key: string,
  fetcher: () => Promise<unknown>,
  options: UseCachedDataOptions = {},
): UseCachedDataReturn {
  const { ttl = 5 * 60 * 1000, fallback = null } = options;
  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadCachedData = async (): Promise<void> => {
      try {
        const cached = localStorage.getItem(`cache_${key}`);
        if (cached) {
          const parsed = JSON.parse(cached) as { data: unknown; timestamp: number };
          if (Date.now() - parsed.timestamp < ttl) {
            setData(parsed.data);
            setLoading(false);
            return;
          }
        }

        const freshData = await fetcher();
        setData(freshData);

        localStorage.setItem(
          `cache_${key}`,
          JSON.stringify({ data: freshData, timestamp: Date.now() }),
        );
      } catch (error) {
        logger.error('Cache error:', error);
        if (fallback) {
          setData(fallback);
        }
      } finally {
        setLoading(false);
      }
    };

    loadCachedData();
  }, [key, fetcher, ttl, fallback]);

  const clearCache = useCallback((): void => {
    localStorage.removeItem(`cache_${key}`);
  }, [key]);

  return { data, loading, clearCache };
}
