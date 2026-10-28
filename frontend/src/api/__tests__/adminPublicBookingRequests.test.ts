import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));

vi.mock('../client', () => ({ api: { get, post } }));

const requestDto = {
  id: 'd0552c55-0a77-4c7f-a6de-22580d270ab5',
  patient_id: 987654,
  patient_display_name: 'SYNTHETIC Patient',
  service_name: 'SYNTHETIC Consultation',
  doctor_display_name: 'SYNTHETIC Doctor',
  service_slug: 'synthetic-service',
  doctor_slug: 'synthetic-doctor',
  appointment_date: '2026-11-04',
  appointment_time: '10:20:00',
  appointment_id: null,
  timezone: 'Asia/Tashkent',
  status: 'pending',
  settings_version: 2,
  version: 7,
  created_at: '2026-10-28T08:15:00+05:00',
  updated_at: '2026-10-28T08:15:00+05:00',
  history: [],
};

import {
  confirmStaffPublicBookingRequest,
  getStaffBookingRequestErrorCode,
  listStaffPublicBookingRequests,
  rejectPublicBookingRequest,
  requestNewTimeForPublicBookingRequest,
  STAFF_BOOKING_REQUEST_PAGE_SIZE,
} from '../adminPublicBookingRequests';

describe('Admin/Registrar public booking request API adapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists one status page through the staff-only endpoint', async () => {
    get.mockResolvedValue({ data: { items: [requestDto] } });

    await expect(listStaffPublicBookingRequests({ status: 'pending' })).resolves.toEqual([{
      id: requestDto.id,
      patientDisplayName: requestDto.patient_display_name,
      serviceName: requestDto.service_name,
      doctorDisplayName: requestDto.doctor_display_name,
      serviceSlug: requestDto.service_slug,
      doctorSlug: requestDto.doctor_slug,
      appointmentDate: requestDto.appointment_date,
      appointmentTime: requestDto.appointment_time,
      status: requestDto.status,
      version: requestDto.version,
      createdAt: requestDto.created_at,
    }]);
    expect(get).toHaveBeenCalledWith('/admin/public-booking-requests', {
      params: { status: 'pending', limit: STAFF_BOOKING_REQUEST_PAGE_SIZE, offset: 0 },
    });
  });

  it('uses the returned version for every state-changing operation', async () => {
    post.mockResolvedValue({ data: { ...requestDto, status: 'confirmed' } });

    await confirmStaffPublicBookingRequest('request-1', 4);
    await requestNewTimeForPublicBookingRequest('request-1', 5);
    await rejectPublicBookingRequest('request-1', 6);

    expect(post).toHaveBeenNthCalledWith(
      1,
      '/admin/public-booking-requests/request-1/confirm',
      { expected_version: 4 },
    );
    expect(post).toHaveBeenNthCalledWith(
      2,
      '/admin/public-booking-requests/request-1/request-new-time',
      { expected_version: 5 },
    );
    expect(post).toHaveBeenNthCalledWith(
      3,
      '/admin/public-booking-requests/request-1/reject',
      { expected_version: 6 },
    );
  });

  it('extracts only a typed API error code and ignores free-form server detail', () => {
    expect(getStaffBookingRequestErrorCode({
      isAxiosError: true,
      response: { data: { detail: { code: 'booking_request_state_conflict' } } },
    })).toBe('booking_request_state_conflict');
    expect(getStaffBookingRequestErrorCode({
      isAxiosError: true,
      response: { data: { detail: 'internal server message' } },
    })).toBeNull();
    expect(getStaffBookingRequestErrorCode(new Error('network failure'))).toBeNull();
  });
});
