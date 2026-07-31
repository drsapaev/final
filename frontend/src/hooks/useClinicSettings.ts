/**
 * useClinicSettings — hook for clinic settings + ticket print settings.
 *
 * Per ADR-0015, components must NOT import from `api/adminSettings` or
 * `api/ticketPrintSettings` directly. This hook is the sanctioned entry
 * point for both resources, which are co-consumed by ClinicSettings.tsx.
 *
 * Note: this hook does NOT own loading/saving/error state — it only exposes
 * stable callbacks that wrap the API module functions. The component keeps
 * its existing state machine because clinic settings has complex array
 * response parsing + logo upload that doesn't fit the generic
 * useAdminSettings shape.
 */

import { useCallback } from 'react';
import { api } from '../api/client';
import {
  fetchClinicSettings as fetchClinicSettingsApi,
  saveClinicSettings as saveClinicSettingsApi,
} from '../api/adminSettings';
import {
  fetchTicketPrintSettings as fetchTicketPrintSettingsApi,
  saveTicketPrintSettings as saveTicketPrintSettingsApi,
  TICKET_PRINT_SETTINGS_DEFAULTS,
  TICKET_PRINT_SETTINGS_DEFINITIONS,
  normalizeTicketPrintSettings,
} from '../api/ticketPrintSettings';

// Re-export the constants and normalizer so components don't need to import
// from api/ticketPrintSettings directly (ADR-0015).
export {
  TICKET_PRINT_SETTINGS_DEFAULTS,
  TICKET_PRINT_SETTINGS_DEFINITIONS,
  normalizeTicketPrintSettings,
};

export interface ClinicSettingItem {
  key: string;
  value: string;
}

export interface UseClinicSettingsReturn {
  fetchClinicSettings: (category?: string) => Promise<ClinicSettingItem[]>;
  saveClinicSettings: (payload: Record<string, unknown>) => Promise<unknown>;
  fetchTicketPrintSettings: () => Promise<Record<string, unknown>>;
  saveTicketPrintSettings: (payload: Record<string, unknown>) => Promise<unknown>;
  uploadLogo: (file: File) => Promise<string>;
}

export function useClinicSettings(): UseClinicSettingsReturn {
  const fetchClinicSettings = useCallback(async (category = 'clinic'): Promise<ClinicSettingItem[]> => {
    const data = await fetchClinicSettingsApi(category);
    return Array.isArray(data) ? (data as ClinicSettingItem[]) : [];
  }, []);

  const saveClinicSettings = useCallback(async (payload: Record<string, unknown>): Promise<unknown> => {
    return saveClinicSettingsApi(payload);
  }, []);

  const fetchTicketPrintSettings = useCallback(async (): Promise<Record<string, unknown>> => {
    const data = await fetchTicketPrintSettingsApi();
    return data as Record<string, unknown>;
  }, []);

  const saveTicketPrintSettings = useCallback(async (payload: Record<string, unknown>): Promise<unknown> => {
    return saveTicketPrintSettingsApi(payload);
  }, []);

  const uploadLogo = useCallback(async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/admin/clinic/logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data.logo_url as string;
  }, []);

  return {
    fetchClinicSettings,
    saveClinicSettings,
    fetchTicketPrintSettings,
    saveTicketPrintSettings,
    uploadLogo,
  };
}

export default useClinicSettings;
