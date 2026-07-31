/**
 * useLabReporting — hook wrapper for the lab reporting API.
 *
 * Per ADR-0015, components must NOT import from `api/labReporting` directly.
 * This hook is the sanctioned entry point.
 *
 * Same pattern as useMcpClient: the API client (`api/labReporting.ts:
 * labReportingApi`) is a stable singleton object. The hook returns it via
 * the hook layer, enforcing the import boundary without adding boilerplate.
 *
 * Components should call:
 *   const labApi = useLabReporting();
 *   const reports = await labApi.getLabReports();
 *
 * Tests that mock `api/labReporting` continue to work because the hook
 * returns the same object reference.
 */

import { labReportingApi } from '../api/labReporting';

export type LabReportingAPI = typeof labReportingApi;

export function useLabReporting(): LabReportingAPI {
  // labReportingApi is a stable singleton (module-level const).
  return labReportingApi;
}

export default useLabReporting;
