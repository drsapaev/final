import { api } from './client';
import { mapCalendarRescheduledVisitDto } from './mappers/appointment';
import type { CalendarRescheduledVisitDto } from '../types/api';
import type { CalendarRescheduledVisit } from '../types/domain/clinic';

export async function listRescheduledCalendarVisits(day: string): Promise<CalendarRescheduledVisit[]> {
  const { data } = await api.get<CalendarRescheduledVisitDto[]>('/appointments/rescheduled-visits', {
    params: { day },
  });
  return data.map(mapCalendarRescheduledVisitDto);
}
