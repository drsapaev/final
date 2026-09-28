/**
 * RQ-17 — minimal QueueResource admin contract (frontend service module).
 *
 * Backend surface (runtime-PR `codex/rq17-runtime-setup-path`, brief
 * `RQ17_SETUP_PATH_BRIEF.md` §6(1) / §3.2):
 *   GET    /queue/admin/queue-resources          (Admin-only)
 *   GET    /queue/admin/queue-resources/{id}     (Admin-only)
 *   POST   /queue/admin/queue-resources          (draft-by-default; active=true → §3.1 gate)
 *   PATCH  /queue/admin/queue-resources/{id}     (ordinary fields; `code`/`queue_tag` immutable → 422;
 *                                                 `active` lifecycle under serialization-scope §3.1(б))
 *
 * Mutability contract §3.2 is enforced server-side (`extra="forbid"` DTO):
 * the update payload below intentionally has NO `code`/`queue_tag` fields.
 */

import { api } from './client';

export interface QueueResourceDto {
  id: number;
  code: string;
  queue_tag: string;
  display_name: string;
  active: boolean;
  start_number_online: number;
  max_online_per_day: number;
  default_cabinet: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  [key: string]: unknown;
}

export interface QueueResourceCreatePayload {
  code: string;
  queue_tag: string;
  display_name: string;
  start_number_online?: number;
  max_online_per_day?: number;
  default_cabinet?: string | null;
  /** Draft-by-default (S-14: услуги/профиль → draft-ресурс → активация через gate §3.1). */
  active?: boolean;
}

export interface QueueResourceUpdatePayload {
  display_name?: string;
  start_number_online?: number;
  max_online_per_day?: number;
  default_cabinet?: string | null;
  /** Lifecycle-переход под serialization-scope §3.1(б) — gate на active=true. */
  active?: boolean;
}

type AxiosLike = {
  get: (url: string) => Promise<{ data: unknown }>;
  post: (url: string, data: unknown) => Promise<{ data: unknown }>;
  patch: (url: string, data: unknown) => Promise<{ data: unknown }>;
};

const http = api as unknown as AxiosLike;

/** FastAPI error normalization: `{detail: string}` → human-readable text. */
export function queueResourceErrorText(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallback;
}

export async function listQueueResources(activeOnly = false): Promise<QueueResourceDto[]> {
  const url = activeOnly
    ? '/queue/admin/queue-resources?active_only=true'
    : '/queue/admin/queue-resources';
  const response = await http.get(url);
  return (Array.isArray(response.data) ? response.data : []) as QueueResourceDto[];
}

export async function getQueueResource(resourceId: number): Promise<QueueResourceDto> {
  const response = await http.get(`/queue/admin/queue-resources/${resourceId}`);
  return response.data as QueueResourceDto;
}

export async function createQueueResource(
  payload: QueueResourceCreatePayload,
): Promise<QueueResourceDto> {
  const response = await http.post('/queue/admin/queue-resources', payload);
  return response.data as QueueResourceDto;
}

export async function updateQueueResource(
  resourceId: number,
  payload: QueueResourceUpdatePayload,
): Promise<QueueResourceDto> {
  const response = await http.patch(`/queue/admin/queue-resources/${resourceId}`, payload);
  return response.data as QueueResourceDto;
}
