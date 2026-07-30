/**
 * useApiResource<T> — generic hook for async data fetching.
 *
 * Eliminates boilerplate of useState<T[]>([]) + useState<string | null>(null)
 * + useState(false) for loading in every data hook.
 *
 * Usage:
 *   const { state, refetch } = useApiResource(
 *     () => api.get('/patients').then(r => r.data),
 *   );
 *
 *   // With zod schema validation:
 *   const { state } = useApiResource(
 *     () => api.get('/patients/1').then(r => r.data),
 *     { schema: PatientSchema }
 *   );
 *
 *   if (state.status === 'loading') return <Spinner />;
 *   if (state.status === 'error') return <ErrorView error={state.error} />;
 *   if (state.status === 'success') return <PatientView patient={state.data} />;
 */

import { useState, useEffect, useCallback } from 'react';
import type { AsyncState } from '../types/async-state';
import { idleState, loadingState, successState, errorState } from '../types/async-state';
import type { ZodType } from 'zod';

interface UseApiResourceOptions<T> {
  schema?: ZodType<T>;
  enabled?: boolean;
  deps?: unknown[];
}

export function useApiResource<T>(
  fetcher: () => Promise<T>,
  options: UseApiResourceOptions<T> = {}
): {
  state: AsyncState<T>;
  refetch: () => void;
  setData: (data: T) => void;
  reset: () => void;
} {
  const { schema, enabled = true, deps = [] } = options;
  const [state, setState] = useState<AsyncState<T>>(idleState<T>());
  const [refetchCount, setRefetchCount] = useState(0);

  const refetch = useCallback(() => {
    setRefetchCount(c => c + 1);
  }, []);

  const setData = useCallback((data: T) => {
    setState(successState(data));
  }, []);

  const reset = useCallback(() => {
    setState(idleState());
  }, []);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    setState(loadingState<T>());

    fetcher()
      .then((data) => {
        if (cancelled) return;
        if (schema) {
          const result = schema.safeParse(data);
          if (!result.success) {
            setState(errorState<T>(`Validation failed: ${result.error.issues[0]?.message ?? 'unknown'}`));
            return;
          }
          setState(successState(result.data));
        } else {
          setState(successState(data));
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : String(err);
        setState(errorState<T>(message));
      });

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, refetchCount, ...deps]);

  return { state, refetch, setData, reset };
}
