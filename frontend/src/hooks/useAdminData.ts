import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import axios from 'axios';
import type { AsyncState } from '../types/async-state';
import { idleState, loadingState, successState, errorState, getError } from '../types/async-state';

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
  const [requestState, setRequestState] = useState<AsyncState<unknown>>(idleState<unknown>());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef<boolean>(true);

  const loading = requestState.status === 'loading';
  const error = getError(requestState);

  const onErrorRef = useRef(onError);
  const onSuccessRef = useRef(onSuccess);

  useEffect(() => {
    onErrorRef.current = onError;
    onSuccessRef.current = onSuccess;
  });

  const fetchData = useCallback(async (): Promise<void> => {
    if (!enabled || !url || !mountedRef.current) return;

    // audit/phase-4, BS-13: previously a new AbortController was created and
    // stored in the ref, but its `signal` was NEVER passed to `api.get()`.
    // Cleanup aborted nothing — in-flight requests completed on the network
    // and ran `setData`/`onSuccessRef` even after unmount (only `mountedRef`
    // prevented the state update, not the wasted bandwidth/CPU). Two fixes:
    //   1. Abort the PREVIOUS controller before creating a new one — without
    //      this, rapid re-fetches (e.g., refreshInterval tick during a slow
    //      request) accumulated multiple in-flight requests.
    //   2. Pass `{ signal }` to axios so the request actually gets cancelled.
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const currentAbortController = new AbortController();
    abortControllerRef.current = currentAbortController;

    try {
      setRequestState(loadingState<unknown>());

      const cleanUrl = url.startsWith('/api/v1') ? url.replace('/api/v1', '') : url;
      const response = await api.get(cleanUrl, { signal: currentAbortController.signal });

      if (!mountedRef.current) return;
      setData(response.data);
      setRequestState(successState<unknown>(null));
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

      if (!mountedRef.current) return;
      setRequestState(errorState<unknown>(String(err)));
      onErrorRef.current(err);
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
