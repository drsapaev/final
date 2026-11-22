import { api } from './client';
import type {
  PublicBookingCalendarConfirmDto,
  PublicBookingCalendarUpdateDto,
  PublicBookingCalendarYearDto,
} from '../types/api';

export type PublicBookingCalendarYear = PublicBookingCalendarYearDto;
export type PublicBookingCalendarUpdate = PublicBookingCalendarUpdateDto;
export type PublicBookingCalendarConfirm = PublicBookingCalendarConfirmDto;

const calendarPath = (year: number) => `/admin/public-booking-calendar/${year}`;

export async function getPublicBookingCalendar(year: number): Promise<PublicBookingCalendarYear> {
  const response = await api.get<PublicBookingCalendarYear>(calendarPath(year));
  return response.data;
}

export async function updatePublicBookingCalendar(
  year: number,
  update: PublicBookingCalendarUpdate,
): Promise<PublicBookingCalendarYear> {
  const response = await api.put<PublicBookingCalendarYear>(calendarPath(year), update);
  return response.data;
}

export async function confirmPublicBookingCalendar(
  year: number,
  confirmation: PublicBookingCalendarConfirm,
): Promise<PublicBookingCalendarYear> {
  const response = await api.post<PublicBookingCalendarYear>(
    `${calendarPath(year)}/confirm`,
    confirmation,
  );
  return response.data;
}
