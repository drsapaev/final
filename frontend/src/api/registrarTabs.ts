import { api } from './client';

export type RegistrarTabTargetKind = 'profile' | 'doctor';

export interface ResolvedRegistrarTab {
  target_kind: RegistrarTabTargetKind;
  target_id: number;
  custom_title: string | null;
  title: string;
  title_ru: string | null;
  profile_key: string | null;
  queue_tags: string[];
  icon: string | null;
  color: string | null;
  visible: boolean;
  available: boolean;
  reason_code: string | null;
}

export interface RegistrarTabsResponse {
  mode: 'legacy' | 'configured';
  version: number;
  tabs: ResolvedRegistrarTab[];
  profile_filters: RegistrarProfileFilter[];
}

export interface RegistrarProfileFilter {
  key: string;
  queue_tags: string[];
  title: string;
  title_ru: string | null;
}

export interface AdminRegistrarTabsResponse extends RegistrarTabsResponse {
  options: ResolvedRegistrarTab[];
}

export interface RegistrarTabInput {
  target_kind: RegistrarTabTargetKind;
  target_id: number;
  title: string | null;
  visible: boolean;
}

export interface RegistrarTabsUpdate {
  expected_version: number;
  tabs: RegistrarTabInput[];
  reason: 'configure_registrar_tabs';
}

export const registrarTabIdentity = (tab: Pick<RegistrarTabInput, 'target_kind' | 'target_id'>): string =>
  `${tab.target_kind}:${tab.target_id}`;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

const isNullableString = (value: unknown): value is string | null =>
  value === null || typeof value === 'string';

function readTabs(value: unknown): ResolvedRegistrarTab[] {
  if (!Array.isArray(value)) throw new Error('Invalid registrar tab list');
  const identities = new Set<string>();
  return value.map((item: unknown) => {
    if (!isRecord(item)
      || (item.target_kind !== 'profile' && item.target_kind !== 'doctor')
      || !Number.isSafeInteger(item.target_id) || Number(item.target_id) <= 0
      || typeof item.title !== 'string'
      || !isNullableString(item.custom_title)
      || !isNullableString(item.title_ru)
      || !isNullableString(item.profile_key)
      || !isNullableString(item.icon)
      || !isNullableString(item.color)
      || !isNullableString(item.reason_code)
      || typeof item.visible !== 'boolean' || typeof item.available !== 'boolean'
      || !Array.isArray(item.queue_tags) || !item.queue_tags.every((tag: unknown) => typeof tag === 'string')) {
      throw new Error('Invalid registrar tab');
    }
    const tab = item as unknown as ResolvedRegistrarTab;
    const identity = registrarTabIdentity(tab);
    if (identities.has(identity)) throw new Error('Duplicate registrar tab');
    identities.add(identity);
    return tab;
  });
}

function readResponse(value: unknown): RegistrarTabsResponse {
  if (!isRecord(value) || (value.mode !== 'legacy' && value.mode !== 'configured')
    || !Number.isSafeInteger(value.version) || Number(value.version) < 0) {
    throw new Error('Invalid registrar tabs response');
  }
  if (!Array.isArray(value.profile_filters) || value.profile_filters.some((filter: unknown) =>
    !isRecord(filter) || typeof filter.key !== 'string' || typeof filter.title !== 'string'
    || !isNullableString(filter.title_ru) || !Array.isArray(filter.queue_tags)
    || !filter.queue_tags.every((tag: unknown) => typeof tag === 'string'))) {
    throw new Error('Invalid registrar profile filters');
  }
  return {
    mode: value.mode,
    version: Number(value.version),
    tabs: readTabs(value.tabs),
    profile_filters: value.profile_filters as RegistrarProfileFilter[],
  };
}

function readAdminResponse(value: unknown): AdminRegistrarTabsResponse {
  const response = readResponse(value);
  if (!isRecord(value)) throw new Error('Invalid registrar tabs response');
  return { ...response, options: readTabs(value.options) };
}

export async function getRegistrarTabs(): Promise<RegistrarTabsResponse> {
  const response = await api.get<unknown>('/registrar/tabs');
  return readResponse(response.data);
}

export async function getAdminRegistrarTabs(): Promise<AdminRegistrarTabsResponse> {
  const response = await api.get<unknown>('/admin/registrar-tabs');
  return readAdminResponse(response.data);
}

export async function saveRegistrarTabs(update: RegistrarTabsUpdate): Promise<AdminRegistrarTabsResponse> {
  const response = await api.put<unknown>('/admin/registrar-tabs', update);
  return readAdminResponse(response.data);
}
