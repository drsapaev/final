/**
 * NURSE-V2 N2-5 — the hook wrapper over the serving-plane API module.
 *
 * ADR-0015: components never import `@/api/*` directly; this hook is the
 * injection point (and the future place for telemetry/cancellation if the
 * tablet slice grows).
 */

import {
  callNextPatient,
  completeServiceExecution,
  getStationBoard,
  incompleteServiceExecution,
  listDrainingExecutions,
  listWorkplaces,
  markEntryIncomplete,
  markEntryNoShow,
  nurseServingErrorStatus,
  nurseServingErrorText,
  startEntry,
  startServiceExecution,
} from '@/api/nurseServing';

export type NurseServingApi = {
  listWorkplaces: typeof listWorkplaces;
  getStationBoard: typeof getStationBoard;
  listDrainingExecutions: typeof listDrainingExecutions;
  callNextPatient: typeof callNextPatient;
  startEntry: typeof startEntry;
  startServiceExecution: typeof startServiceExecution;
  completeServiceExecution: typeof completeServiceExecution;
  incompleteServiceExecution: typeof incompleteServiceExecution;
  markEntryNoShow: typeof markEntryNoShow;
  markEntryIncomplete: typeof markEntryIncomplete;
  nurseServingErrorStatus: typeof nurseServingErrorStatus;
  nurseServingErrorText: typeof nurseServingErrorText;
};

export function useNurseServingApi(): NurseServingApi {
  return {
    listWorkplaces,
    getStationBoard,
    listDrainingExecutions,
    callNextPatient,
    startEntry,
    startServiceExecution,
    completeServiceExecution,
    incompleteServiceExecution,
    markEntryNoShow,
    markEntryIncomplete,
    nurseServingErrorStatus,
    nurseServingErrorText,
  };
}
