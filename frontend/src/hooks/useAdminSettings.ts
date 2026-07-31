/**
 * useAdminSettings — generic hook for admin settings CRUD operations.
 *
 * Per ADR-0015 (Domain Boundary Matrix), components must NOT import from
 * `api/adminSettings` directly. This hook is the only sanctioned entry
 * point for the 5 admin settings resources:
 *
 *   - wizard settings       (fetchWizardSettings / saveWizardSettings)
 *   - benefit settings      (fetchBenefitSettings / saveBenefitSettings)
 *   - clinic settings       (fetchClinicSettings / saveClinicSettings)
 *   - ticket print settings (fetchTicketPrintSettings / saveTicketPrintSettings)
 *   - payment provider      (fetchPaymentProviderSettings / savePaymentProviderSettings
 *                            + testPaymentProviderConfig)
 *
 * The hook is generic over T (the settings shape). Callers pass a pair
 * of (fetch, save) functions; the hook owns loading/saving/error state
 * and exposes a stable reload + save API.
 *
 * Usage:
 *   const {
 *     settings, originalSettings, loading, saving, error, lastUpdated,
 *     reload, save, reset,
 *   } = useAdminSettings({
 *     fetchFn: fetchBenefitSettings,
 *     saveFn: saveBenefitSettings,
 *     errorMessage: t('admin2.bs_error_load_settings'),
 *   });
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'react-toastify';
import logger from '../utils/logger';
import { getErrorMessage } from '../utils/type-guards';
// ADR-0015: hooks are the sanctioned layer to import from api/* modules.
import {
  fetchBenefitSettings,
  saveBenefitSettings,
  fetchClinicSettings,
  saveClinicSettings,
  fetchWizardSettings,
  saveWizardSettings,
  fetchTicketPrintSettings,
  saveTicketPrintSettings,
  fetchPaymentProviderSettings,
  savePaymentProviderSettings,
} from '../api/adminSettings';

/**
 * Pre-configured fetch/save pairs for each admin settings resource.
 * Components pick one of these — they never import api/adminSettings directly.
 */
export const ADMIN_SETTINGS_RESOURCES = {
  benefit: {
    fetch: fetchBenefitSettings,
    save: saveBenefitSettings,
  },
  clinic: {
    fetch: () => fetchClinicSettings('clinic'),
    save: saveClinicSettings,
  },
  wizard: {
    fetch: fetchWizardSettings,
    save: saveWizardSettings,
  },
  ticketPrint: {
    fetch: fetchTicketPrintSettings,
    save: saveTicketPrintSettings,
  },
  paymentProvider: {
    fetch: fetchPaymentProviderSettings,
    save: savePaymentProviderSettings,
  },
} as const;

export type AdminSettingsResource = keyof typeof ADMIN_SETTINGS_RESOURCES;

export interface UseAdminSettingsOptions<T> {
  /** Resource key — pick from ADMIN_SETTINGS_RESOURCES. */
  resource: AdminSettingsResource;
  /**
   * Optional override for the fetch function. Use only if the resource
   * list above doesn't fit (e.g. clinic settings with a non-default
   * category). When provided, takes precedence over `resource`.
   */
  fetchFn?: () => Promise<T>;
  /** Optional override for the save function. */
  saveFn?: (payload: T) => Promise<unknown>;
  /** Error message shown when fetch fails. */
  errorMessage: string;
  /** Toast message shown when fetch fails. Optional — pass empty string to skip. */
  loadErrorToast?: string;
  /** Toast message shown when save succeeds. Optional — pass empty string to skip. */
  saveSuccessToast?: string;
  /** Toast message shown when save fails. Optional — pass empty string to skip. */
  saveErrorToast?: string;
  /** Auto-load on mount. Default: true. */
  autoLoad?: boolean;
}

export interface UseAdminSettingsReturn<T> {
  settings: T | null;
  originalSettings: T | null;
  loading: boolean;
  saving: boolean;
  error: string | null;
  lastUpdated: Date | null;
  /** Reload settings from the server. */
  reload: () => Promise<void>;
  /** Save settings. Returns true on success. */
  save: (payload: T) => Promise<boolean>;
  /** Reset error state. */
  resetError: () => void;
}

export function useAdminSettings<T extends Record<string, unknown>>(
  options: UseAdminSettingsOptions<T>,
): UseAdminSettingsReturn<T> {
  const {
    resource,
    fetchFn: fetchFnOverride,
    saveFn: saveFnOverride,
    errorMessage,
    loadErrorToast,
    saveSuccessToast,
    saveErrorToast,
    autoLoad = true,
  } = options;

  // Resolve fetch/save functions from the resource key (or override).
  const fetchFn = fetchFnOverride ?? (ADMIN_SETTINGS_RESOURCES[resource].fetch as () => Promise<T>);
  const saveFn = saveFnOverride ?? (ADMIN_SETTINGS_RESOURCES[resource].save as (payload: T) => Promise<unknown>);

  const [settings, setSettings] = useState<T | null>(null);
  const [originalSettings, setOriginalSettings] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(autoLoad);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Refs to keep callbacks stable without re-running useEffect.
  const fetchFnRef = useRef(fetchFn);
  const saveFnRef = useRef(saveFn);
  const errorMessageRef = useRef(errorMessage);
  const loadErrorToastRef = useRef(loadErrorToast);
  const saveSuccessToastRef = useRef(saveSuccessToast);
  const saveErrorToastRef = useRef(saveErrorToast);

  useEffect(() => {
    fetchFnRef.current = fetchFn;
    saveFnRef.current = saveFn;
    errorMessageRef.current = errorMessage;
    loadErrorToastRef.current = loadErrorToast;
    saveSuccessToastRef.current = saveSuccessToast;
    saveErrorToastRef.current = saveErrorToast;
  }, [fetchFn, saveFn, errorMessage, loadErrorToast, saveSuccessToast, saveErrorToast]);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFnRef.current();
      setSettings(data);
      setOriginalSettings(data);
      const updatedAt = (data as { updated_at?: unknown })?.updated_at;
      setLastUpdated(updatedAt ? new Date(String(updatedAt)) : null);
    } catch (err) {
      logger.error('useAdminSettings: load failed', err);
      setError(getErrorMessage(err) || errorMessageRef.current);
      if (loadErrorToastRef.current) {
        toast.error(loadErrorToastRef.current);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const save = useCallback(async (payload: T): Promise<boolean> => {
    setSaving(true);
    setError(null);
    try {
      await saveFnRef.current(payload);
      setSettings(payload);
      setOriginalSettings(payload);
      setLastUpdated(new Date());
      if (saveSuccessToastRef.current) {
        toast.success(saveSuccessToastRef.current);
      }
      return true;
    } catch (err) {
      logger.error('useAdminSettings: save failed', err);
      const msg = getErrorMessage(err) || errorMessageRef.current;
      setError(msg);
      if (saveErrorToastRef.current) {
        toast.error(saveErrorToastRef.current);
      }
      return false;
    } finally {
      setSaving(false);
    }
  }, []);

  const resetError = useCallback(() => setError(null), []);

  useEffect(() => {
    if (autoLoad) {
      void reload();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    settings,
    originalSettings,
    loading,
    saving,
    error,
    lastUpdated,
    reload,
    save,
    resetError,
  };
}

export default useAdminSettings;
