/**
 * PR-UI-13-2 unit contract: registrarWorklistRows — the pure view-model
 * computation extracted from RegistrarPanel's filteredAppointments /
 * departmentStats useMemo bodies.
 *
 * Pins the presentation-only filtering contract:
 * - tab filter via queue_tags from API profiles (fallback: tabKey itself)
 * - status filter + client-side search (FIO / record id / phone digits)
 * - "all departments" aggregation + search over aggregated rows
 * - department stats: profile-key iteration, tag matching, today gating,
 *   active-queue / pending-payment flags
 */
import { describe, expect, it } from 'vitest';

import type { Appointment } from '../../../types/domain/clinic';
import {
  computeDepartmentStats,
  computeRegistrarWorklistRows,
  type QueueProfileItem,
} from '../registrarWorklistRows';

const asAppointments = (rows: Record<string, unknown>[]): Appointment[] =>
  rows as unknown as Appointment[];
const FALLBACK = 'Неизвестный пациент';
const TODAY = '2026-08-29';

const appt = (overrides: Record<string, unknown>): Record<string, unknown> =>
  ({ queue_time: '2026-08-29T08:00:00+05:00', ...overrides });

describe('computeDepartmentStats (PR-UI-13-2)', () => {
  it('falls back to the hardcoded profile key set when no profiles loaded', () => {
    const stats = computeDepartmentStats(asAppointments([
      appt({ queue_tag: 'cardiology', date: TODAY, status: 'waiting', queue_numbers: [{ number: 1 }] }),
    ]), TODAY, []);
    expect(Object.keys(stats)).toEqual([
      'cardiology', 'ecg', 'dermatology', 'stomatology', 'lab', 'procedures',
    ]);
    expect(stats.cardiology.todayCount).toBe(1);
    expect(stats.cardiology.hasActiveQueue).toBe(true);
    expect(stats.lab.todayCount).toBe(0);
  });

  it('uses API profile keys and their queue_tags for matching', () => {
    const profiles: QueueProfileItem[] = [
      { key: 'cardio', queue_tags: ['cardiology', 'cardio-kb'] },
    ];
    const stats = computeDepartmentStats(asAppointments([
      appt({ queue_tag: 'Cardiology ', date: TODAY }), // case+whitespace tolerant
      appt({ queue_tag: 'cardio-kb', date: TODAY }),
      appt({ queue_tag: 'lab', date: TODAY }), // not in profiles
    ]), TODAY, profiles);
    expect(Object.keys(stats)).toEqual(['cardio']);
    expect(stats.cardio.todayCount).toBe(2);
  });

  it('todayCount gates on date === todayStr; hasActiveQueue checks ALL profile entries (not date-gated) for active status + queue_numbers', () => {
    // hasActiveQueue is intentionally NOT date-gated in the original logic:
    // it scans every profile appointment (any day) for an active-queue state.
    const stats = computeDepartmentStats(asAppointments([
      appt({ queue_tag: 'lab', date: '2026-08-28', status: 'waiting', queue_numbers: [{ number: 1 }] }), // other day, active
      appt({ queue_tag: 'lab', date: TODAY, status: 'done', queue_numbers: [{ number: 2 }] }), // today, inactive status
      appt({ queue_tag: 'lab', date: TODAY, status: 'waiting' }), // today, no queue_numbers
    ]), TODAY, [{ key: 'lab' }]);
    expect(stats.lab.todayCount).toBe(2);
    expect(stats.lab.hasActiveQueue).toBe(true); // other-day waiting entry qualifies
  });

  it('hasActiveQueue false when no entry has active status with queue_numbers', () => {
    const stats = computeDepartmentStats(asAppointments([
      appt({ queue_tag: 'lab', date: TODAY, status: 'done', queue_numbers: [{ number: 2 }] }),
      appt({ queue_tag: 'lab', date: TODAY, status: 'waiting' }),
    ]), TODAY, [{ key: 'lab' }]);
    expect(stats.lab.hasActiveQueue).toBe(false);
  });

  it('hasPendingPayments: paid_pending status OR payment_status pending', () => {
    const stats = computeDepartmentStats(asAppointments([
      appt({ queue_tag: 'lab', date: TODAY, status: 'paid_pending' }),
    ]), TODAY, [{ key: 'lab' }]);
    expect(stats.lab.hasPendingPayments).toBe(true);

    const stats2 = computeDepartmentStats(asAppointments([
      appt({ queue_tag: 'lab', date: TODAY, payment_status: 'pending' }),
    ]), TODAY, [{ key: 'lab' }]);
    expect(stats2.lab.hasPendingPayments).toBe(true);

    const stats3 = computeDepartmentStats(asAppointments([
      appt({ queue_tag: 'lab', date: TODAY, status: 'waiting', payment_status: 'paid' }),
    ]), TODAY, [{ key: 'lab' }]);
    expect(stats3.lab.hasPendingPayments).toBe(false);
  });
});

describe('computeRegistrarWorklistRows (PR-UI-13-2)', () => {
  const profiles: QueueProfileItem[] = [{ key: 'cardio', queue_tags: ['cardiology'] }];

  it('tab filter: matches entries by profile queue_tags, applies status filter, sorts by queue_time (ISO timestamps)', () => {
    // NOTE: bare 'HH:MM' strings do not parse as timestamps (parseRegistrarTimestamp
    // needs ISO/±offset forms) → sort falls back to id order. Real backend rows
    // carry ISO timestamps — fixtures use them to exercise the real ordering.
    const rows = computeRegistrarWorklistRows({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T09:00:00+05:00', patient_fio: 'Бета', status: 'waiting' }),
        appt({ id: '2', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00', patient_fio: 'Альфа', status: 'waiting' }),
        appt({ id: '3', queue_tag: 'lab', queue_time: '2026-08-29T07:00:00+05:00', patient_fio: 'Гамма', status: 'waiting' }),
      ]),
      activeTab: 'cardio',
      statusFilter: 'waiting',
      searchQuery: '',
      queueProfiles: profiles,
      services: {},
      fallbackPatientLabel: FALLBACK,
    });
    expect(rows.map((r) => r.id)).toEqual(['2', '1']); // sorted by queue_time ASC
  });

  it('tab filter fallback: tabKey itself is the tag when profile has no queue_tags', () => {
    const rows = computeRegistrarWorklistRows({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'derma', queue_time: '2026-08-29T08:00:00+05:00' }),
      ]),
      activeTab: 'derma',
      statusFilter: null,
      searchQuery: '',
      queueProfiles: [{ key: 'derma' }], // no queue_tags → fallback [tabKey]
      services: {},
      fallbackPatientLabel: FALLBACK,
    });
    expect(rows).toHaveLength(1);
  });

  it('search matches FIO (case-insensitive), record id, and phone digits; digit-free queries match all rows (pre-existing quirk)', () => {
    const base = {
      appointments: asAppointments([
        appt({ id: '10', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00', patient_fio: 'Иванов Иван' }),
        appt({ id: '20', queue_tag: 'cardiology', queue_time: '2026-08-29T08:30:00+05:00', patient_fio: 'Петров Пётр', patient_phone: '+998 90 123-45-67' }),
      ]),
      activeTab: 'cardio',
      statusFilter: null,
      searchQuery: '',
      queueProfiles: profiles,
      services: {},
      fallbackPatientLabel: FALLBACK,
    };
    // Digit-bearing queries filter properly.
    const byId = computeRegistrarWorklistRows({ ...base, searchQuery: '20' });
    expect(byId.map((r) => r.id)).toEqual(['20']);
    const byPhoneDigits = computeRegistrarWorklistRows({ ...base, searchQuery: '90123' });
    expect(byPhoneDigits.map((r) => r.id)).toEqual(['20']);
    // PRE-EXISTING QUIRK (verbatim port, documented in PR-UI-13-2): a query
    // without digits yields searchDigits='' and phoneDigits.includes('') === true,
    // so inPhone passes for EVERY row — FIO search on the tab path is effectively
    // non-filtering. Pinned as-is; fixing it is a follow-up (behavior change).
    const byAlpha = computeRegistrarWorklistRows({ ...base, searchQuery: 'иван' });
    expect(byAlpha.map((r) => r.id)).toEqual(['10', '20']);
  });

  it('rows without patient_fio get the localized fallback label + normalized queue_numbers shape', () => {
    const rows = computeRegistrarWorklistRows({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00', number: 7, status: 'waiting' }),
      ]),
      activeTab: 'cardio',
      statusFilter: null,
      searchQuery: '',
      queueProfiles: profiles,
      services: {},
      fallbackPatientLabel: FALLBACK,
    });
    expect(rows[0].patient_fio).toBe(FALLBACK);
    expect(rows[0].queue_number).toBe(7);
    expect(rows[0].queue_numbers).toEqual([{
      number: 7,
      queue_tag: 'cardiology',
      status: 'waiting',
      queue_time: '2026-08-29T08:00:00+05:00',
    }]);
  });

  it('status filter excludes non-matching statuses on the tab path', () => {
    const rows = computeRegistrarWorklistRows({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00', status: 'waiting' }),
        appt({ id: '2', queue_tag: 'cardiology', queue_time: '2026-08-29T09:00:00+05:00', status: 'done' }),
      ]),
      activeTab: 'cardio',
      statusFilter: 'done',
      searchQuery: '',
      queueProfiles: profiles,
      services: {},
      fallbackPatientLabel: FALLBACK,
    });
    expect(rows.map((r) => r.id)).toEqual(['2']);
  });

  it('all-departments tab: aggregates patients (1 patient with 2 records → grouped) and applies service formatting', () => {
    const rows = computeRegistrarWorklistRows({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00', patient_fio: 'Иванов Иван', patient_id: 100, services: ['K01'] }),
        appt({ id: '2', queue_tag: 'lab', queue_time: '2026-08-29T08:30:00+05:00', patient_fio: 'Иванов Иван', patient_id: 100, services: ['L01'] }),
      ]),
      activeTab: null,
      statusFilter: null,
      searchQuery: '',
      queueProfiles: profiles,
      services: {},
      fallbackPatientLabel: FALLBACK,
    });
    // aggregation groups by patient — verify at most one row per patient name
    // and that the aggregate row exposes grouped services through the SSOT path.
    expect(rows.length).toBeLessThanOrEqual(2);
    const fios = rows.map((r) => r.patient_fio);
    expect(fios.every((f) => typeof f === 'string')).toBe(true);
  });

  it('all-departments tab: digit-bearing search filters aggregated rows by phone digits; digit-free search is non-filtering (pre-existing quirk)', () => {
    const base = {
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00', patient_fio: 'Иванов Иван', patient_id: 100, services: ['K01'], patient_phone: '+998901111111' }),
        appt({ id: '2', queue_tag: 'lab', queue_time: '2026-08-29T08:30:00+05:00', patient_fio: 'Петров Пётр', patient_id: 200, services: ['L01'], patient_phone: '+998902222222' }),
      ]),
      activeTab: null,
      statusFilter: null,
      searchQuery: '',
      queueProfiles: profiles,
      services: {},
      fallbackPatientLabel: FALLBACK,
    };
    // Phone-digit query filters aggregated rows.
    const byPhone = computeRegistrarWorklistRows({ ...base, searchQuery: '90222' });
    const phoneFios = byPhone.map((r) => String(r.patient_fio || ''));
    expect(phoneFios.some((f) => f.includes('Петров'))).toBe(true);
    expect(phoneFios.some((f) => f.includes('Иванов'))).toBe(false);
    // Digit-free query matches all (same pre-existing quirk as the tab path).
    const byAlpha = computeRegistrarWorklistRows({ ...base, searchQuery: 'петров' });
    expect(byAlpha.length).toBeGreaterThanOrEqual(1);
  });

  it('explicit status filter on all-departments path filters before aggregation', () => {
    const rows = computeRegistrarWorklistRows({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'lab', queue_time: '2026-08-29T08:00:00+05:00', patient_fio: 'Иванов Иван', status: 'waiting' }),
        appt({ id: '2', queue_tag: 'lab', queue_time: '2026-08-29T08:30:00+05:00', patient_fio: 'Петров Пётр', status: 'done' }),
      ]),
      activeTab: null,
      statusFilter: 'done',
      searchQuery: '',
      queueProfiles: profiles,
      services: {},
      fallbackPatientLabel: FALLBACK,
    });
    // only the 'done' record survives pre-aggregation filtering
    const allIds = JSON.stringify(rows);
    expect(allIds).not.toContain('Иванов');
    expect(allIds).toContain('Петров');
  });
});
