import { isAxiosError } from 'axios';
import { api } from './client';
import type {
  PublicBookingRequestActionDto,
  PublicBookingRequestPatientOutDto,
  PublicBookingRequestStaffListOutDto,
  PublicBookingRequestStatusDto,
} from '../types/api';

export const STAFF_BOOKING_REQUEST_PAGE_SIZE = 50;

const requestsPath = '/admin/public-booking-requests';

export type StaffBookingRequestStatus = PublicBookingRequestStatusDto;

export interface StaffPublicBookingRequest {
  id: string;
  patientDisplayName: string;
  serviceName: string;
  doctorDisplayName: string;
  serviceSlug: string;
  doctorSlug: string;
  appointmentDate: string;
  appointmentTime: string;
  status: StaffBookingRequestStatus;
  version: number;
  createdAt: string;
}

function toStaffPublicBookingRequest(
  request: PublicBookingRequestPatientOutDto,
): StaffPublicBookingRequest {
  return {
    id: request.id,
    patientDisplayName: request.patient_display_name,
    serviceName: request.service_name,
    doctorDisplayName: request.doctor_display_name,
    serviceSlug: request.service_slug,
    doctorSlug: request.doctor_slug,
    appointmentDate: request.appointment_date,
    appointmentTime: request.appointment_time,
    status: request.status,
    version: request.version,
    createdAt: request.created_at,
  };
}

export interface StaffBookingRequestListQuery {
  status: PublicBookingRequestStatusDto;
  offset?: number;
  limit?: number;
}

export async function listStaffPublicBookingRequests(
  query: StaffBookingRequestListQuery,
): Promise<StaffPublicBookingRequest[]> {
  const response = await api.get<PublicBookingRequestStaffListOutDto>(requestsPath, {
    params: {
      status: query.status,
      limit: query.limit ?? STAFF_BOOKING_REQUEST_PAGE_SIZE,
      offset: query.offset ?? 0,
    },
  });
  return response.data.items.map(toStaffPublicBookingRequest);
}

export async function confirmStaffPublicBookingRequest(
  requestId: string,
  expectedVersion: number,
): Promise<StaffPublicBookingRequest> {
  const body: PublicBookingRequestActionDto = { expected_version: expectedVersion };
  const response = await api.post<PublicBookingRequestPatientOutDto>(
    `${requestsPath}/${encodeURIComponent(requestId)}/confirm`,
    body,
  );
  return toStaffPublicBookingRequest(response.data);
}

export async function requestNewTimeForPublicBookingRequest(
  requestId: string,
  expectedVersion: number,
): Promise<StaffPublicBookingRequest> {
  const body: PublicBookingRequestActionDto = { expected_version: expectedVersion };
  const response = await api.post<PublicBookingRequestPatientOutDto>(
    `${requestsPath}/${encodeURIComponent(requestId)}/request-new-time`,
    body,
  );
  return toStaffPublicBookingRequest(response.data);
}

export async function rejectPublicBookingRequest(
  requestId: string,
  expectedVersion: number,
): Promise<StaffPublicBookingRequest> {
  const body: PublicBookingRequestActionDto = { expected_version: expectedVersion };
  const response = await api.post<PublicBookingRequestPatientOutDto>(
    `${requestsPath}/${encodeURIComponent(requestId)}/reject`,
    body,
  );
  return toStaffPublicBookingRequest(response.data);
}

export function getStaffBookingRequestErrorCode(error: unknown): string | null {
  if (!isAxiosError(error)) return null;
  const detail = error.response?.data?.detail;
  if (!detail || typeof detail !== 'object' || !('code' in detail)) return null;
  const code = (detail as { code?: unknown }).code;
  return typeof code === 'string' ? code : null;
}
