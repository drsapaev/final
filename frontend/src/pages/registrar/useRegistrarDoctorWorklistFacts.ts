import { useMemo } from 'react';
import type { Appointment, Doctor } from '../../types/domain/clinic';
import { computeDoctorStats } from './registrarWorklistRows';

/** Presentation facts for per-doctor tabs; the backend owns queue identity. */
export const useRegistrarDoctorWorklistFacts = ({
  appointments, doctors, activeDoctorId, showCalendar, historyDate,
  urlDate, todayStr, tI18n,
}: {
  appointments: Appointment[];
  doctors: Doctor[];
  activeDoctorId: number | null;
  showCalendar: boolean;
  historyDate: string;
  urlDate: string | null;
  todayStr: string;
  tI18n: (key: string, options?: Record<string, unknown>) => string;
}) => useMemo(() => {
  const date = showCalendar && historyDate ? historyDate : urlDate || todayStr;
  const selectedDoctor = doctors.find((doctor) => Number(doctor.id) === activeDoctorId);
  const selectedDoctorLabel = activeDoctorId != null
    ? selectedDoctor?.user?.full_name || selectedDoctor?.full_name || selectedDoctor?.name ||
      tI18n('registrarPanel.qs_doctor_fallback', { id: activeDoctorId })
    : null;
  return {
    selectedDoctorLabel,
    doctorStats: computeDoctorStats(appointments, date, doctors.map((doctor) => Number(doctor.id))),
    doctorCountLabel: date === todayStr ? tI18n('registrarPanel.today') : date,
  };
}, [appointments, doctors, activeDoctorId, showCalendar, historyDate, urlDate, todayStr, tI18n]);

export default useRegistrarDoctorWorklistFacts;
