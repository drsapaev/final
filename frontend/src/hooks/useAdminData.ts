import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import axios from 'axios';

interface UseAdminDataOptions {
  refreshInterval?: number;
  onError?: (err: unknown) => void;
  onSuccess?: (data: unknown) => void;
  initialData?: unknown;
  enabled?: boolean;
}

interface UseAdminDataReturn {
  data: unknown;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  refetch: () => void;
}

const useAdminData = (
  url: string,
  options: UseAdminDataOptions = {},
): UseAdminDataReturn => {
  const {
    refreshInterval = 0,
    onError = () => {},
    onSuccess = () => {},
    initialData = null,
    enabled = true,
  } = options;

  const [data, setData] = useState<unknown>(initialData);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef<boolean>(true);

  const onErrorRef = useRef(onError);
  const onSuccessRef = useRef(onSuccess);

  useEffect(() => {
    onErrorRef.current = onError;
    onSuccessRef.current = onSuccess;
  });

  const fetchData = useCallback(async (): Promise<void> => {
    if (!enabled || !url || !mountedRef.current) return;

    const currentAbortController = new AbortController();
    abortControllerRef.current = currentAbortController;

    try {
      setLoading(true);
      setError(null);

      const cleanUrl = url.startsWith('/api/v1') ? url.replace('/api/v1', '') : url;
      const response = await api.get(cleanUrl);

      setData(response.data);
      onSuccessRef.current(response.data);
    } catch (err) {
      const errorObj = err as Error & { name: string };
      if (
        errorObj?.name === 'AbortError' ||
        errorObj?.name === 'CanceledError' ||
        axios.isCancel(err)
      ) {
        return;
      }

      setError(String(err));
      onErrorRef.current(err);
    } finally {
      setLoading(false);
    }
  }, [url, enabled]);

  const refresh = useCallback((): void => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (enabled && url) {
      fetchData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, url]);

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
    refetch: refresh,
  };
};

export default useAdminData;
