import { isAxiosError } from 'axios';
import { api } from './client';
import type {
  PublicBookingAvailabilityDto,
  PublicBookingOptionsDto,
  PublicBookingRequestCreateDto,
  PublicBookingRequestListOutDto,
  PublicBookingRequestOutDto,
  PublicBookingRequestPatientOutDto,
  PublicBookingRequestStatusDto,
} from '../types/api';

export type PublicBookingLocale = 'ru' | 'uz-Latn';

export type PublicBookingOptions = PublicBookingOptionsDto;
export type PublicBookingAvailability = PublicBookingAvailabilityDto;
export type PublicBookingRequestBody = PublicBookingRequestCreateDto;
export type PublicBookingRequestResult = PublicBookingRequestPatientOutDto;

export interface PublicBookingRequestResubmitBody {
  expected_version: number;
  appointment_date: string;
  appointment_time: string;
  expected_settings_version: number;
}

export interface PublicBookingSelection {
  locale: PublicBookingLocale;
  serviceSlug: string;
  doctorSlug: string;
  date: string;
  time: string;
  settingsVersion: number;
  createdAt: number;
}

export type PublicBookingResume =
  | { kind: 'selection'; selection: PublicBookingSelection }
  | { kind: 'expired'; locale: PublicBookingLocale };

export const PUBLIC_BOOKING_SELECTION_TTL_MS = 15 * 60 * 1000;

const optionsPath = '/public-site/booking-options';
const availabilityPath = '/public-site/availability';
const patientRequestsPath = '/patients/booking-requests';

export type PatientPublicBookingRequest = PublicBookingRequestOutDto;
export type PatientPublicBookingRequestStatus = PublicBookingRequestStatusDto;

export async function listPatientPublicBookingRequests(input: {
  limit?: number;
  offset?: number;
} = {}): Promise<PatientPublicBookingRequest[]> {
  const response = await api.get<PublicBookingRequestListOutDto>(patientRequestsPath, {
    params: { limit: input.limit ?? 50, offset: input.offset ?? 0 },
    headers: { 'Cache-Control': 'no-cache' },
  });
  return response.data.items;
}

export async function withdrawPatientPublicBookingRequest(
  requestId: string,
  expectedVersion: number,
): Promise<PatientPublicBookingRequest> {
  const response = await api.post<PatientPublicBookingRequest>(
    `${patientRequestsPath}/${encodeURIComponent(requestId)}/withdraw`,
    { expected_version: expectedVersion },
  );
  return response.data;
}

export async function resubmitPatientPublicBookingRequest(
  requestId: string,
  body: PublicBookingRequestResubmitBody,
  idempotencyKey: string,
): Promise<PatientPublicBookingRequest> {
  const response = await api.post<PatientPublicBookingRequest>(
    `${patientRequestsPath}/${encodeURIComponent(requestId)}/resubmit`,
    body,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  );
  return response.data;
}

let pendingResume: PublicBookingResume | null = null;

function isLocale(value: unknown): value is PublicBookingLocale {
  return value === 'ru' || value === 'uz-Latn';
}

function isDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function isTime(value: unknown): value is string {
  return typeof value === 'string' && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
}

function isSelection(value: unknown): value is PublicBookingSelection {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<PublicBookingSelection>;
  return isLocale(candidate.locale)
    && typeof candidate.serviceSlug === 'string'
    && candidate.serviceSlug.length > 0
    && candidate.serviceSlug.length <= 120
    && typeof candidate.doctorSlug === 'string'
    && candidate.doctorSlug.length > 0
    && candidate.doctorSlug.length <= 120
    && isDate(candidate.date)
    && isTime(candidate.time)
    && Number.isSafeInteger(candidate.settingsVersion)
    && (candidate.settingsVersion ?? -1) >= 0
    && Number.isSafeInteger(candidate.createdAt)
    && (candidate.createdAt ?? 0) > 0;
}

export async function getPublicBookingOptions(
  locale: PublicBookingLocale,
  signal?: AbortSignal,
): Promise<PublicBookingOptions> {
  const response = await api.get<PublicBookingOptions>(optionsPath, {
    params: { locale },
    headers: { 'Cache-Control': 'no-cache' },
    signal,
  });
  return response.data;
}

export async function getPublicBookingAvailability(input: {
  serviceSlug: string;
  doctorSlug: string;
  date: string;
  signal?: AbortSignal;
}): Promise<PublicBookingAvailability> {
  const response = await api.get<PublicBookingAvailability>(availabilityPath, {
    params: {
      service_slug: input.serviceSlug,
      doctor_slug: input.doctorSlug,
      date: input.date,
    },
    headers: { 'Cache-Control': 'no-cache' },
    signal: input.signal,
  });
  return response.data;
}

export async function createPatientPublicBookingRequest(
  body: PublicBookingRequestBody,
  idempotencyKey: string,
): Promise<PublicBookingRequestResult> {
  const response = await api.post<PublicBookingRequestResult>(
    patientRequestsPath,
    body,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  );
  return response.data;
}

/** Keep selection only in this tab's memory while a patient signs in or activates a card. */
export function savePublicBookingSelection(selection: PublicBookingSelection): void {
  if (!isSelection(selection)) {
    pendingResume = null;
    return;
  }
  pendingResume = { kind: 'selection', selection: { ...selection } };
}

/** Return the localized destination without exposing the selection in a URL or history state. */
export function getPendingPublicBookingLocale(now = Date.now()): PublicBookingLocale | null {
  if (!pendingResume) return null;
  if (pendingResume.kind === 'selection'
    && (now < pendingResume.selection.createdAt
      || now - pendingResume.selection.createdAt > PUBLIC_BOOKING_SELECTION_TTL_MS)) {
    pendingResume = { kind: 'expired', locale: pendingResume.selection.locale };
  }
  return pendingResume.kind === 'selection'
    ? pendingResume.selection.locale
    : pendingResume.locale;
}

/** Consume once after authentication; expired selection data is discarded before returning. */
export function takePendingPublicBookingResume(now = Date.now()): PublicBookingResume | null {
  const current = pendingResume;
  pendingResume = null;
  if (!current) return null;
  if (current.kind === 'expired') return current;
  if (now < current.selection.createdAt
    || now - current.selection.createdAt > PUBLIC_BOOKING_SELECTION_TTL_MS) {
    return { kind: 'expired', locale: current.selection.locale };
  }
  return current;
}

export function clearPendingPublicBookingSelection(): void {
  pendingResume = null;
}

export function getPublicBookingErrorCode(error: unknown): string | null {
  if (!isAxiosError(error)) return null;
  const data = error.response?.data;
  if (!data || typeof data !== 'object') return null;
  const payload = data as { code?: unknown; detail?: unknown };
  if (typeof payload.code === 'string') return payload.code;
  if (payload.detail && typeof payload.detail === 'object') {
    const detail = payload.detail as { code?: unknown; reason?: unknown };
    if (typeof detail.code === 'string') return detail.code;
    if (detail.reason === 'patient_profile_required') return detail.reason;
  }
  return null;
}

export function isUnknownPublicBookingOutcome(error: unknown): boolean {
  if (!isAxiosError(error)) return true;
  const code = getPublicBookingErrorCode(error);
  return code === 'idempotency_uncertain_outcome'
    || code === 'idempotency_in_flight'
    || !error.response
    || (error.response?.status ?? 0) >= 500;
}

export function createPublicBookingIdempotencyKey(): string {
  const cryptoApi = globalThis.crypto;
  if (typeof cryptoApi?.randomUUID === 'function') return cryptoApi.randomUUID();
  if (typeof cryptoApi?.getRandomValues !== 'function') {
    throw new Error('Secure randomness is unavailable.');
  }
  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function getPublicBookingPath(locale: PublicBookingLocale): string {
  return locale === 'ru' ? '/ru/booking' : '/booking';
}
