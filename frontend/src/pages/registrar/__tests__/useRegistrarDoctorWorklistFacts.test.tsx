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
      loadedDate: '2026-09-20',
      tI18n: (key) => key,
    }));
    expect(result.current.selectedDoctorLabel).toBe('Петров Пётр');
    expect(result.current.doctorCountLabel).toBe('2026-09-20');
    expect(result.current.doctorStats['7'].todayCount).toBe(1);
    expect(result.current.doctorStats['8'].todayCount).toBe(0);
  });

  // REG-FE-027 (registrar audit ledger) + PR #3851 review (P2): the Welcome
  // morning checklist is a TODAY-only instrument — the hook must expose
  // whether the VERIFIED sample (loadedDate: the target_date of the last
  // successful load) is the current clinic day. It must NOT key off the
  // selected date: during a «history → today» switch the old sample is
  // still on screen while the new request is in flight.
  it('flags whether the loaded sample is the current clinic day (sampleIsToday)', () => {
    const base = {
      appointments: [] as Appointment[],
      doctors: [] as Doctor[],
      activeDoctorId: null,
      tI18n: (key: string) => key,
    };
    // Calendar history mode on a past day, sample verified for that day → NOT today.
    const history = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: true, historyDate: '2026-09-20', urlDate: null, todayStr: '2026-09-25',
      loadedDate: '2026-09-20',
    }));
    expect(history.result.current.sampleIsToday).toBe(false);
    // Calendar open on today, sample verified for today → today.
    const calendarToday = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: true, historyDate: '2026-09-25', urlDate: null, todayStr: '2026-09-25',
      loadedDate: '2026-09-25',
    }));
    expect(calendarToday.result.current.sampleIsToday).toBe(true);
    // URL date on a past day (calendar closed), sample verified → NOT today.
    const urlPast = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: false, historyDate: '', urlDate: '2026-09-20', todayStr: '2026-09-25',
      loadedDate: '2026-09-20',
    }));
    expect(urlPast.result.current.sampleIsToday).toBe(false);
    // No date anywhere, sample verified for the clinic today → today.
    const today = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: false, historyDate: '', urlDate: null, todayStr: '2026-09-25',
      loadedDate: '2026-09-25',
    }));
    expect(today.result.current.sampleIsToday).toBe(true);
  });

  // PR #3851 review (P2) regression: the «history → today» transition. The
  // selected date flips to today instantly, but the sample still belongs to
  // the historical day (request in flight, or failed and kept stale, RQ-22)
  // — sampleIsToday must stay false until a today-sample is VERIFIED.
  it('sampleIsToday stays false while the selected date is today but the verified sample is not', () => {
    const base = {
      appointments: [{ id: 1 }] as unknown as Appointment[],
      doctors: [] as Doctor[],
      activeDoctorId: null,
      tI18n: (key: string) => key,
    };
    // Calendar switched to today; today's load still in flight — the rows on
    // screen are yesterday's VERIFIED sample.
    const transition = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: true, historyDate: '2026-09-25', urlDate: null, todayStr: '2026-09-25',
      loadedDate: '2026-09-24',
    }));
    expect(transition.result.current.sampleIsToday).toBe(false);
    // Nothing verified yet (initial load in flight) → honest false, even
    // though the selection resolves to today.
    const unverified = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: false, historyDate: '', urlDate: null, todayStr: '2026-09-25',
      loadedDate: null,
    }));
    expect(unverified.result.current.sampleIsToday).toBe(false);
    // The selected URL date can even differ from the loaded day — the flag
    // describes the SAMPLE, not the selection.
    const sampleTodaySelectionHistory = renderHook(() => useRegistrarDoctorWorklistFacts({
      ...base, showCalendar: true, historyDate: '2026-09-20', urlDate: null, todayStr: '2026-09-25',
      loadedDate: '2026-09-25',
    }));
    expect(sampleTodaySelectionHistory.result.current.sampleIsToday).toBe(true);
  });
});
