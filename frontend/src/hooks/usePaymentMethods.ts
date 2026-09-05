/**
 * usePaymentMethods — hook for loading payment methods.
 *
 * UX Audit R-4.3 (Phase 2): backend-driven payment methods.
 *
 * Currently uses DEFAULT_PAYMENT_METHODS from config.
 * Backend endpoint: GET /api/v1/payments/payment-methods.
 * this hook will fetch from API with fallback to defaults.
 *
 * Usage:
 *   const { paymentMethods, loading, error } = usePaymentMethods();
 *
 * Future migration:
 * 1. (this PR) Hook returns DEFAULT_PAYMENT_METHODS synchronously
 * 2. (next PR) Hook fetches from API with useEffect
 * 3. (final) Backend endpoint returns dynamic payment methods per clinic
 */
import { useState, useEffect } from 'react';
import { DEFAULT_PAYMENT_METHODS, mapBackendPaymentMethods } from '../config/paymentMethods';
import { api } from '../api/client';
import logger from '../utils/logger';
import type { AsyncState } from '../types/async-state';
import { idleState, loadingState, successState, errorState, getData, getError } from '../types/async-state';

export function usePaymentMethods(options: Record<string, unknown> = {}) {
  const { enableBackendFetch = false } = options;

  const [paymentMethodsState, setPaymentMethodsState] = useState<AsyncState<typeof DEFAULT_PAYMENT_METHODS>>(idleState<typeof DEFAULT_PAYMENT_METHODS>());

  const paymentMethods = getData(paymentMethodsState, DEFAULT_PAYMENT_METHODS);
  const loading = paymentMethodsState.status === 'loading';
  const error = getError(paymentMethodsState);

  useEffect(() => {
    if (!enableBackendFetch) return;

    let cancelled = false;
    const fetchPaymentMethods = async () => {
      setPaymentMethodsState(loadingState<typeof DEFAULT_PAYMENT_METHODS>());
      try {
        const response = await api.get('/payments/payment-methods');
        if (!cancelled) {
          // If backend returns no methods, fall back to defaults — getData
          // returns the fallback automatically when state is not 'success',
          // but here we explicitly transition to success with the mapped or
          // default set so loading=false.
          const methods = response.data?.methods;
          const mapped = methods
            ? (mapBackendPaymentMethods(methods) as typeof DEFAULT_PAYMENT_METHODS)
            : DEFAULT_PAYMENT_METHODS;
          setPaymentMethodsState(successState<typeof DEFAULT_PAYMENT_METHODS>(mapped));
        }
      } catch (err) {
        if (!cancelled) {
          logger.warn('[usePaymentMethods] Failed to fetch from backend, using defaults:', err);
          // getData returns DEFAULT_PAYMENT_METHODS fallback when state is
          // 'error', so callers still get the default list while seeing the
          // error message — preserving the original hook's dual-return shape.
          setPaymentMethodsState(errorState<typeof DEFAULT_PAYMENT_METHODS>(String(err)));
        }
      }
    };

    fetchPaymentMethods();
    return () => { cancelled = true; };
  }, [enableBackendFetch]);

  return { paymentMethods, loading, error };
}

export default usePaymentMethods;
