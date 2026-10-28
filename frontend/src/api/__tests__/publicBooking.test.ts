import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

import { api } from '../client';
import {
  clearPendingPublicBookingSelection,
  createPatientPublicBookingRequest,
  getPendingPublicBookingLocale,
  getPublicBookingAvailability,
  getPublicBookingErrorCode,
  getPublicBookingOptions,
  getPublicBookingPath,
  isUnknownPublicBookingOutcome,
  savePublicBookingSelection,
  takePendingPublicBookingResume,
  PUBLIC_BOOKING_SELECTION_TTL_MS,
} from '../publicBooking';

const mockedApi = vi.mocked(api);

describe('publicBooking API adapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearPendingPublicBookingSelection();
  });

  it('uses the existing public options and no-cache availability contracts', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: { settings_version: 3 } });
    mockedApi.get.mockResolvedValueOnce({ data: { date: '2026-10-28', timezone: 'Asia/Tashkent', settings_version: 3, slots: ['09:00:00'] } });

    await getPublicBookingOptions('ru');
    await getPublicBookingAvailability({ serviceSlug: 'cardiology', doctorSlug: 'doctor-one', date: '2026-10-28' });

    expect(mockedApi.get).toHaveBeenNthCalledWith(1, '/public-site/booking-options', {
      params: { locale: 'ru' },
      headers: { 'Cache-Control': 'no-cache' },
      signal: undefined,
    });
    expect(mockedApi.get).toHaveBeenNthCalledWith(2, '/public-site/availability', {
      params: { service_slug: 'cardiology', doctor_slug: 'doctor-one', date: '2026-10-28' },
      headers: { 'Cache-Control': 'no-cache' },
      signal: undefined,
    });
  });

  it('posts only public slugs and selected time with the mandatory idempotency key', async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { id: 'request-id' } });
    const body = {
      service_slug: 'cardiology',
      doctor_slug: 'doctor-one',
      appointment_date: '2026-10-28',
      appointment_time: '09:00',
      expected_settings_version: 3,
    };

    await createPatientPublicBookingRequest(body, 'key-once');

    expect(mockedApi.post).toHaveBeenCalledWith('/patients/booking-requests', body, {
      headers: { 'Idempotency-Key': 'key-once' },
    });
    expect(body).not.toHaveProperty('patient_id');
  });

  it('keeps a short-lived selection only in memory and consumes it once', () => {
    const now = 1_800_000_000_000;
    const selection = {
      locale: 'ru' as const,
      serviceSlug: 'cardiology',
      doctorSlug: 'doctor-one',
      date: '2026-10-28',
      time: '09:00',
      settingsVersion: 3,
      createdAt: now,
    };
    savePublicBookingSelection(selection);

    expect(getPendingPublicBookingLocale(now + 1)).toBe('ru');
    expect(takePendingPublicBookingResume(now + 1)).toEqual({ kind: 'selection', selection });
    expect(takePendingPublicBookingResume(now + 2)).toBeNull();

    savePublicBookingSelection(selection);
    expect(takePendingPublicBookingResume(now + PUBLIC_BOOKING_SELECTION_TTL_MS + 1))
      .toEqual({ kind: 'expired', locale: 'ru' });
  });

  it('maps structured API errors and treats ambiguous outcomes as unsafe to resubmit with a new key', () => {
    const conflict = {
      isAxiosError: true,
      response: { status: 409, data: { detail: { code: 'booking_time_unavailable' } } },
    };
    const ambiguous = { isAxiosError: true, request: {} };
    const rejected = {
      isAxiosError: true,
      response: { status: 422, data: { detail: { code: 'booking_time_unavailable' } } },
    };

    expect(getPublicBookingErrorCode(conflict)).toBe('booking_time_unavailable');
    expect(isUnknownPublicBookingOutcome(ambiguous)).toBe(true);
    expect(isUnknownPublicBookingOutcome(rejected)).toBe(false);
    expect(getPublicBookingPath('ru')).toBe('/ru/booking');
    expect(getPublicBookingPath('uz-Latn')).toBe('/booking');
  });
});
