import { useMemo } from 'react';
import type { Appointment, Doctor } from '../../types/domain/clinic';
import { computeDoctorStats } from './registrarWorklistRows';

/** Presentation facts for per-doctor tabs; the backend owns queue identity. */
export const useRegistrarDoctorWorklistFacts = ({
  appointments, doctors, activeDoctorId, showCalendar, historyDate,
  urlDate, todayStr, loadedDate, tI18n,
}: {
  appointments: Appointment[];
  doctors: Doctor[];
  activeDoctorId: number | null;
  showCalendar: boolean;
  historyDate: string;
  urlDate: string | null;
  todayStr: string;
  /** PR #3851 review (P2): the clinic day of the VERIFIED sample from
   *  useRegistrarWorklistData (target_date of the last successful load).
   *  NOT the selected date: on a date switch the selection changes
   *  instantly while the sample still belongs to the previous day, and a
   *  failed refresh (RQ-22) keeps those rows on screen — today-only
   *  instruments must not present them as the current clinic day. */
  loadedDate: string | null;
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
    // REG-FE-027 (registrar audit ledger) + PR #3851 review (P2): does the
    // VERIFIED sample belong to the current clinic day? Bound to
    // `loadedDate` (the target_date of the last SUCCESSFUL load), never to
    // the selected date: on a «history → today» switch the old sample is
    // kept while the request is in flight, and a failed load keeps it with
    // stale=true — the Welcome morning checklist must not render those
    // rows as today's. null (nothing verified yet) → honest false.
    sampleIsToday: loadedDate != null && loadedDate === todayStr,
  };
}, [appointments, doctors, activeDoctorId, showCalendar, historyDate, urlDate, todayStr, loadedDate, tI18n]);

export default useRegistrarDoctorWorklistFacts;
