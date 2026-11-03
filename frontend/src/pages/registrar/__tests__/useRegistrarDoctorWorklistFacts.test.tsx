import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Appointment, Doctor } from '../../../types/domain/clinic';
import { toDoctorId } from '../../../types/domain/branded';
import { useRegistrarDoctorWorklistFacts } from '../useRegistrarDoctorWorklistFacts';

describe('per-doctor worklist presentation facts', () => {
  it('uses the doctor full name, selected date, and actual queue owner even for an empty doctor', () => {
    const doctors = [
      { id: toDoctorId(7), user: { full_name: 'Иванов Иван' } },
      { id: toDoctorId(8), user: { full_name: 'Петров Пётр' } },
    ] as Doctor[];
    const appointments = [
      { id: 1, queue_owner_kind: 'doctor', queue_owner_id: 7, date: '2026-09-20' },
      { id: 2, queue_owner_kind: 'doctor', queue_owner_id: 7, date: '2026-09-25' },
    ] as unknown as Appointment[];
    const { result } = renderHook(() => useRegistrarDoctorWorklistFacts({
      appointments, doctors, activeDoctorId: 8,
      showCalendar: false, historyDate: '', urlDate: '2026-09-20', todayStr: '2026-09-25',
      tI18n: (key) => key,
    }));
    expect(result.current.selectedDoctorLabel).toBe('Петров Пётр');
    expect(result.current.doctorCountLabel).toBe('2026-09-20');
    expect(result.current.doctorStats['7'].todayCount).toBe(1);
    expect(result.current.doctorStats['8'].todayCount).toBe(0);
  });

  // REG-FE-027 (registrar audit ledger): the Welcome morning checklist is a
  // TODAY-only instrument — the hook must expose whether the loaded sample's
  // effective day (calendar historyDate → ?date → clinic today) is today.
  it('flags whether the loaded sample is the current clinic day (sampleIsToday)', () => {
    const base = {
      appointments: [] as Appointment[],
      doctors: [] as Doctor[],
      activeDoctorId: null,
      tI18n: (key: string) => key,
    };
    // Calendar history mode on a past day → NOT today.
    const history = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: true, historyDate: '2026-09-20', urlDate: null, todayStr: '2026-09-25',
    }));
    expect(history.result.current.sampleIsToday).toBe(false);
    // Calendar open on today → today.
    const calendarToday = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: true, historyDate: '2026-09-25', urlDate: null, todayStr: '2026-09-25',
    }));
    expect(calendarToday.result.current.sampleIsToday).toBe(true);
    // URL date on a past day (calendar closed) → NOT today.
    const urlPast = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: false, historyDate: '', urlDate: '2026-09-20', todayStr: '2026-09-25',
    }));
    expect(urlPast.result.current.sampleIsToday).toBe(false);
    // No date anywhere → clinic today.
    const today = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: false, historyDate: '', urlDate: null, todayStr: '2026-09-25',
    }));
    expect(today.result.current.sampleIsToday).toBe(true);
  });
});
