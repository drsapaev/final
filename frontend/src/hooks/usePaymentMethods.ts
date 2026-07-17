/**
 * usePaymentMethods — hook for loading payment methods.
 *
 * UX Audit R-4.3 (Phase 2): backend-driven payment methods.
 *
 * Currently uses DEFAULT_PAYMENT_METHODS from config.
 * When backend endpoint GET /api/v1/payment-methods becomes available,
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

export function usePaymentMethods(options: Record<string, unknown> = {}) {
  const { enableBackendFetch = false } = options;

  const [paymentMethods, setPaymentMethods] = useState(DEFAULT_PAYMENT_METHODS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enableBackendFetch) return;

    let cancelled = false;
    const fetchPaymentMethods = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.get('/payment-methods');
        if (response.data?.methods && !cancelled) {
          const mapped = mapBackendPaymentMethods(response.data.methods);
          setPaymentMethods(mapped);
        }
      } catch (err) {
        if (!cancelled) {
          logger.warn('[usePaymentMethods] Failed to fetch from backend, using defaults:', err);
          setError(err);
          // Fallback to defaults on error
          setPaymentMethods(DEFAULT_PAYMENT_METHODS);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchPaymentMethods();
    return () => { cancelled = true; };
  }, [enableBackendFetch]);

  return { paymentMethods, loading, error };
}

export default usePaymentMethods;
