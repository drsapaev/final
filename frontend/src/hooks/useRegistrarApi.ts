/**
 * useRegistrarApi — hook wrapper for the registrar API module.
 *
 * Per ADR-0015, components must NOT import from `api/registrar` directly.
 * This hook is the sanctioned entry point for:
 *   - fetchPriceOverrides / approvePriceOverride
 *   - fetchRegistrarDoctors / fetchRegistrarQueueSettings
 *   - fetchRegistrarServices
 *
 * Also re-exports the `PriceOverrideEntry` type so components don't need
 * to import it from `api/registrar` directly.
 */

import {
  fetchPriceOverrides,
  approvePriceOverride,
  fetchRegistrarDoctors,
  fetchRegistrarQueueSettings,
  fetchRegistrarServices,
  type PriceOverrideEntry,
} from '../api/registrar';

export type { PriceOverrideEntry };

export interface UseRegistrarApiReturn {
  fetchPriceOverrides: typeof fetchPriceOverrides;
  approvePriceOverride: typeof approvePriceOverride;
  fetchRegistrarDoctors: typeof fetchRegistrarDoctors;
  fetchRegistrarQueueSettings: typeof fetchRegistrarQueueSettings;
  fetchRegistrarServices: typeof fetchRegistrarServices;
}

export function useRegistrarApi(): UseRegistrarApiReturn {
  return {
    fetchPriceOverrides,
    approvePriceOverride,
    fetchRegistrarDoctors,
    fetchRegistrarQueueSettings,
    fetchRegistrarServices,
  };
}

export default useRegistrarApi;
