import { api } from './client';
import { mapCalendarRescheduledVisitDto } from './mappers/appointment';
import type { CalendarRescheduledVisitDto, DoctorInfoResponseDto } from '../types/api';
import type { CalendarRescheduledVisit } from '../types/domain/clinic';

export async function listRescheduledCalendarVisits(day: string, doctorId?: number): Promise<CalendarRescheduledVisit[]> {
  const { data } = await api.get<CalendarRescheduledVisitDto[]>('/appointments/rescheduled-visits', {
    params: { day, ...(doctorId == null ? {} : { doctor_id: doctorId }) },
  });
  return data.map(mapCalendarRescheduledVisitDto);
}

export async function getCalendarDoctorId(userId: number): Promise<number> {
  const { data } = await api.get<DoctorInfoResponseDto>(`/doctor-info/doctors/by-user/${encodeURIComponent(userId)}`);
  if (!Number.isSafeInteger(data.id) || data.id <= 0 || !data.is_active) {
    throw new Error('No active doctor profile');
  }
  return data.id;
}
