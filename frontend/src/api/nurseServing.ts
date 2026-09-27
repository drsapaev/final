/**
 * NURSE-V2 — the nurse serving plane API module (N2-5 frontend service).
 *
 * Backend surface (N2-3, PR #3355 + the drain-recovery follow-up #3358):
 *   GET  /nurse/serving/workplaces
 *   GET  /nurse/serving/queue-resources/{id}/entries
 *   POST /nurse/serving/queue-resources/{id}/call-next
 *   POST /nurse/serving/queue-resources/{id}/entries/{entry}/start
 *   POST /nurse/serving/queue-resources/{id}/executions
 *   POST /nurse/serving/executions/{id}/complete
 *   POST /nurse/serving/executions/{id}/incomplete
 *   POST /nurse/serving/queue-resources/{id}/entries/{entry}/no-show
 *   POST /nurse/serving/queue-resources/{id}/entries/{entry}/incomplete
 *   GET  /nurse/serving/draining-executions        (drain-recovery discovery)
 *
 * Contract discipline (the N2-5 brief §3): ONLY this surface — no extra
 * patient/EMR endpoints for a richer UI; the DTOs are the generated
 * openapi-typescript shapes re-exported via `@/types/api` (no handwritten
 * duplicates). Per ADR-0015 components never import this module directly —
 * the `useNurseServingApi` hook wraps it.
 */

import { api } from './client';

import type {
  NurseServingCallNextDto,
  NurseServingDrainingExecutionItemDto,
  NurseServingDrainingExecutionListDto,
  NurseServingEntryActionDto,
  NurseServingExecutionCreateRequestDto,
  NurseServingExecutionDto,
  NurseServingReasonRequestDto,
  NurseServingStartDto,
  NurseServingStationDto,
  NurseServingWorkplaceDto,
  NurseServingWorkplaceListDto,
} from '@/types/api';

export type { NurseServingDrainingExecutionItemDto };

type AxiosLike = {
  get: (url: string) => Promise<{ data: unknown }>;
  post: (url: string, data?: unknown) => Promise<{ data: unknown }>;
};

const http = api as unknown as AxiosLike;

export type NurseWorkplace = NurseServingWorkplaceDto;
export type NurseStationBoard = NurseServingStationDto;
export type NurseBoardEntry = NurseStationBoard['active'][number];
export type NurseStationService = NonNullable<NurseBoardEntry['services']>[number];

// ---------------------------------------------------------------------------
// read plane
// ---------------------------------------------------------------------------

export async function listWorkplaces(): Promise<{
  items: NurseWorkplace[];
  total: number;
}> {
  const response = await http.get('/nurse/serving/workplaces');
  return response.data as NurseServingWorkplaceListDto;
}

export async function getStationBoard(
  queueResourceId: number,
): Promise<NurseStationBoard> {
  const response = await http.get(
    `/nurse/serving/queue-resources/${queueResourceId}/entries`,
  );
  return response.data as NurseStationBoard;
}

export async function listDrainingExecutions(): Promise<NurseServingDrainingExecutionListDto> {
  const response = await http.get('/nurse/serving/draining-executions');
  return response.data as NurseServingDrainingExecutionListDto;
}

// ---------------------------------------------------------------------------
// mutations (the server stays the correctness boundary — §7)
// ---------------------------------------------------------------------------

export async function callNextPatient(
  queueResourceId: number,
): Promise<NurseServingCallNextDto> {
  const response = await http.post(
    `/nurse/serving/queue-resources/${queueResourceId}/call-next`,
  );
  return response.data as NurseServingCallNextDto;
}

export async function startEntry(
  queueResourceId: number,
  entryId: number,
): Promise<NurseServingStartDto> {
  const response = await http.post(
    `/nurse/serving/queue-resources/${queueResourceId}/entries/${entryId}/start`,
  );
  return response.data as NurseServingStartDto;
}

export async function startServiceExecution(
  queueResourceId: number,
  payload: NurseServingExecutionCreateRequestDto,
): Promise<NurseServingExecutionDto> {
  const response = await http.post(
    `/nurse/serving/queue-resources/${queueResourceId}/executions`,
    payload,
  );
  return response.data as NurseServingExecutionDto;
}

export async function completeServiceExecution(
  executionId: number,
): Promise<NurseServingExecutionDto> {
  const response = await http.post(
    `/nurse/serving/executions/${executionId}/complete`,
  );
  return response.data as NurseServingExecutionDto;
}

export async function incompleteServiceExecution(
  executionId: number,
  payload: NurseServingReasonRequestDto,
): Promise<NurseServingExecutionDto> {
  const response = await http.post(
    `/nurse/serving/executions/${executionId}/incomplete`,
    payload,
  );
  return response.data as NurseServingExecutionDto;
}

export async function markEntryNoShow(
  queueResourceId: number,
  entryId: number,
): Promise<NurseServingEntryActionDto> {
  const response = await http.post(
    `/nurse/serving/queue-resources/${queueResourceId}/entries/${entryId}/no-show`,
  );
  return response.data as NurseServingEntryActionDto;
}

export async function markEntryIncomplete(
  queueResourceId: number,
  entryId: number,
  payload: NurseServingReasonRequestDto,
): Promise<NurseServingEntryActionDto> {
  const response = await http.post(
    `/nurse/serving/queue-resources/${queueResourceId}/entries/${entryId}/incomplete`,
    payload,
  );
  return response.data as NurseServingEntryActionDto;
}

// ---------------------------------------------------------------------------
// error helpers (the §9 error UX contract)
// ---------------------------------------------------------------------------

export function nurseServingErrorStatus(err: unknown): number | null {
  const status = (err as { response?: { status?: number } })?.response?.status;
  return typeof status === 'number' ? status : null;
}

export function nurseServingErrorText(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response
    ?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallback;
}
