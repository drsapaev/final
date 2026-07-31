/**
 * usePaymentProviderSettings — specialized hook for payment provider admin settings.
 *
 * Per ADR-0015 (Domain Boundary Matrix), components must NOT import from
 * `api/adminSettings` directly. This hook is the sanctioned entry point for
 * the payment-provider settings resource, which has an extra `testProvider`
 * operation beyond the standard fetch/save lifecycle.
 *
 * Used by: components/admin/PaymentProviderSettings.tsx
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'react-toastify';
import logger from '../utils/logger';
import { getErrorMessage } from '../utils/type-guards';
import {
  fetchPaymentProviderSettings,
  savePaymentProviderSettings,
  testPaymentProviderConfig,
} from '../api/adminSettings';

export interface PaymentProviderSettings {
  default_provider: string;
  enabled_providers: string[];
  click: {
    enabled: boolean;
    service_id: string;
    merchant_id: string;
    secret_key: string;
    base_url: string;
    test_mode: boolean;
  };
  payme: {
    enabled: boolean;
    merchant_id: string;
    secret_key: string;
    base_url: string;
    api_url: string;
    test_mode: boolean;
  };
  [key: string]: unknown;
}

export interface TestProviderResult {
  success: boolean;
  message: string;
  timestamp: string;
}

export interface UsePaymentProviderSettingsOptions {
  loadErrorMessage: string;
  saveSuccessToast: string;
  saveErrorMessage: string;
  testSuccessToast: (provider: string) => string;
  testErrorToast: (provider: string) => string;
  testFinishedFallback: string;
}

export interface UsePaymentProviderSettingsReturn {
  settings: PaymentProviderSettings | null;
  loading: boolean;
  saving: boolean;
  testing: boolean;
  error: string | null;
  testResults: Record<string, TestProviderResult>;
  reload: () => Promise<void>;
  save: (payload: PaymentProviderSettings) => Promise<boolean>;
  testProvider: (providerName: string, config: Record<string, unknown>) => Promise<boolean>;
  resetError: () => void;
}

export function usePaymentProviderSettings(
  options: UsePaymentProviderSettingsOptions,
): UsePaymentProviderSettingsReturn {
  const {
    loadErrorMessage,
    saveSuccessToast,
    saveErrorMessage,
    testSuccessToast,
    testErrorToast,
    testFinishedFallback,
  } = options;

  const [settings, setSettings] = useState<PaymentProviderSettings | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [testing, setTesting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestProviderResult>>({});

  // Refs for stable callbacks.
  const optsRef = useRef(options);
  useEffect(() => {
    optsRef.current = options;
  });

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPaymentProviderSettings();
      setSettings(data as PaymentProviderSettings);
    } catch (err) {
      logger.error('usePaymentProviderSettings: load failed', err);
      setError(getErrorMessage(err) || loadErrorMessage);
    } finally {
      setLoading(false);
    }
  }, [loadErrorMessage]);

  const save = useCallback(async (payload: PaymentProviderSettings): Promise<boolean> => {
    setSaving(true);
    setError(null);
    try {
      await savePaymentProviderSettings(payload);
      setSettings(payload);
      toast.success(saveSuccessToast);
      return true;
    } catch (err) {
      logger.error('usePaymentProviderSettings: save failed', err);
      const msg = getErrorMessage(err) || saveErrorMessage;
      setError(msg);
      toast.error(msg);
      return false;
    } finally {
      setSaving(false);
    }
  }, [saveSuccessToast, saveErrorMessage]);

  const testProvider = useCallback(
    async (providerName: string, config: Record<string, unknown>): Promise<boolean> => {
      setTesting(true);
      try {
        const result = await testPaymentProviderConfig(providerName, config);
        const success = Boolean((result as { success?: unknown })?.success);
        const message =
          (result as { message?: string })?.message ||
          (result as { detail?: string })?.detail ||
          testFinishedFallback;
        setTestResults((prev) => ({
          ...prev,
          [providerName]: {
            success,
            message,
            timestamp: new Date().toLocaleString(),
          },
        }));
        if (success) {
          toast.success(testSuccessToast(providerName));
        } else {
          toast.error(testErrorToast(providerName));
        }
        return success;
      } catch (err) {
        logger.error('usePaymentProviderSettings: testProvider failed', err);
        setTestResults((prev) => ({
          ...prev,
          [providerName]: {
            success: false,
            message: getErrorMessage(err) || testFinishedFallback,
            timestamp: new Date().toLocaleString(),
          },
        }));
        toast.error(testErrorToast(providerName));
        return false;
      } finally {
        setTesting(false);
      }
    },
    [testSuccessToast, testErrorToast, testFinishedFallback],
  );

  const resetError = useCallback(() => setError(null), []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    settings,
    loading,
    saving,
    testing,
    error,
    testResults,
    reload,
    save,
    testProvider,
    resetError,
  };
}

export default usePaymentProviderSettings;
