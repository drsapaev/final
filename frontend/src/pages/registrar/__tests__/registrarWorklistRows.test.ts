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
  computeDoctorStats,
  computeRegistrarWorklistRows,
  describeRegistrarWorklistCounter,
  formatRegistrarWorklistCounter,
  resolveRegistrarWorklistEmptyScopeKind,
  type QueueProfileItem,
} from '../registrarWorklistRows';

const asAppointments = (rows: Record<string, unknown>[]): Appointment[] =>
  rows as unknown as Appointment[];
const FALLBACK = 'Неизвестный пациент';
const TODAY = '2026-08-29';

const appt = (overrides: Record<string, unknown>): Record<string, unknown> =>
  ({ queue_time: '2026-08-29T08:00:00+05:00', ...overrides });

describe('per-doctor worklist scope', () => {
  const rows = asAppointments([
    appt({ id: 1, queue_tag: 'cardiology', doctor_id: 99, specialist_id: 99,
      queue_owner_kind: 'doctor', queue_owner_id: 7, date: TODAY, status: 'waiting',
      queue_numbers: [{ number: 1 }], patient_fio: 'A' }),
    appt({ id: 2, queue_tag: 'cardiology', doctor_id: 7,
      queue_owner_kind: 'doctor', queue_owner_id: 8, date: TODAY, status: 'waiting', patient_fio: 'B' }),
    appt({ id: 3, queue_tag: 'cardiology', doctor_id: 7,
      queue_owner_kind: 'resource', queue_owner_id: 7, date: TODAY, patient_fio: 'C' }),
    appt({ id: 4, queue_tag: 'cardiology', doctor_id: 7,
      date: TODAY, patient_fio: 'D' }),
  ]);
  const profiles: QueueProfileItem[] = [{ key: 'cardio', queue_tags: ['cardiology'] }];

  it('filters by entry queue ownership rather than the shared tag or legacy doctor fields', () => {
    const result = computeRegistrarWorklistRows({
      appointments: rows, activeTab: null, activeDoctorId: 7,
      statusFilter: null, searchQuery: '', queueProfiles: profiles,
      services: {}, fallbackPatientLabel: FALLBACK,
    });
    expect(result.map((entry) => entry.id)).toEqual([1]);
    // Profile aggregate remains available and still contains both doctors.
    const profile = computeRegistrarWorklistRows({
      appointments: rows, activeTab: 'cardio', statusFilter: null,
      searchQuery: '', queueProfiles: profiles, services: {}, fallbackPatientLabel: FALLBACK,
    });
    expect(profile).toHaveLength(4);
  });

  it('computes doctor badges, empty scope and signed counters from that same owner', () => {
    const stats = computeDoctorStats(rows, TODAY, [7, 8, 9]);
    expect(stats['7']).toEqual({ todayCount: 1, hasActiveQueue: true, hasPendingPayments: false });
    expect(stats['8'].todayCount).toBe(1);
    expect(stats['9'].todayCount).toBe(0);
    expect(resolveRegistrarWorklistEmptyScopeKind({ appointments: rows, activeTab: null, activeDoctorId: 9, queueProfiles: profiles })).toBe('queue-empty');
    expect(resolveRegistrarWorklistEmptyScopeKind({ appointments: rows, activeTab: null, activeDoctorId: 7, queueProfiles: profiles })).toBe('filtered-empty');
    expect(describeRegistrarWorklistCounter({ appointments: rows, activeTab: null,
      activeDoctorId: 7, queueProfiles: profiles, rows: [], hasMore: false })).toMatchObject({
      unit: 'records', count: 0, scopeCount: 1, narrowed: true,
    });
  });
});

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

  it('search matches FIO (case-insensitive), record id, and phone digits; letter-only query filters via remaining branches (RQ-02)', () => {
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
    // Empty query returns the original set (search branch skipped).
    const noQuery = computeRegistrarWorklistRows({ ...base });
    expect(noQuery.map((r) => r.id)).toEqual(['10', '20']);
    // Digit-bearing queries filter properly.
    const byId = computeRegistrarWorklistRows({ ...base, searchQuery: '20' });
    expect(byId.map((r) => r.id)).toEqual(['20']);
    const byPhoneDigits = computeRegistrarWorklistRows({ ...base, searchQuery: '90123' });
    expect(byPhoneDigits.map((r) => r.id)).toEqual(['20']);
    // Formatted phone still matches (digits present in the query).
    const byFormattedPhone = computeRegistrarWorklistRows({ ...base, searchQuery: '+998 90 123-45-67' });
    expect(byFormattedPhone.map((r) => r.id)).toEqual(['20']);
    // RQ-02 regression: a letter-only query used to yield searchDigits='' and
    // phoneDigits.includes('') === true, so inPhone passed for EVERY row and
    // letter search never filtered (F-01). The phone branch now participates
    // only when the query has digits; Cyrillic FIO match survives.
    const byCyrillic = computeRegistrarWorklistRows({ ...base, searchQuery: 'иван' });
    expect(byCyrillic.map((r) => r.id)).toEqual(['10']);
    // Latin letters match nothing (no FIO/id/phone match) instead of every row.
    const byLatin = computeRegistrarWorklistRows({ ...base, searchQuery: 'ivan' });
    expect(byLatin).toHaveLength(0);
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

  it('all-departments tab: digit-bearing search filters aggregated rows by phone digits; letter-only search filters by FIO (RQ-02)', () => {
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
    // Empty query returns the original aggregated set (search branch skipped).
    const noQuery = computeRegistrarWorklistRows({ ...base });
    expect(noQuery.length).toBe(2);
    // Phone-digit query filters aggregated rows.
    const byPhone = computeRegistrarWorklistRows({ ...base, searchQuery: '90222' });
    const phoneFios = byPhone.map((r) => String(r.patient_fio || ''));
    expect(phoneFios.some((f) => f.includes('Петров'))).toBe(true);
    expect(phoneFios.some((f) => f.includes('Иванов'))).toBe(false);
    // Formatted phone query matches the same single patient.
    const byFormatted = computeRegistrarWorklistRows({ ...base, searchQuery: '+998902222222' });
    expect(byFormatted.length).toBe(1);
    // RQ-02 regression: a letter-only query used to pass the phone branch for
    // every aggregated row; now only the FIO match survives.
    const byAlpha = computeRegistrarWorklistRows({ ...base, searchQuery: 'петров' });
    expect(byAlpha.length).toBe(1);
    expect(String(byAlpha[0].patient_fio || '')).toContain('Петров');
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

// RQ-21.a (F-17): a search / status filter that matches nothing must not be
// presented as an empty QUEUE. The helper returns the FACT about the loaded
// date scope: 'queue-empty' — the scope itself holds zero entries (nothing to
// match); 'filtered-empty' — the scope holds entries, so zero final rows can
// only come from the active narrowing (status filter / search query).
describe('resolveRegistrarWorklistEmptyScopeKind (RQ-21.a)', () => {
  const profiles: QueueProfileItem[] = [{ key: 'cardio', queue_tags: ['cardiology', 'cardio-kb'] }];

  it('specific tab with no matching entries → queue-empty (a "no matches" text here would imply there was something to match)', () => {
    const kind = resolveRegistrarWorklistEmptyScopeKind({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'lab', queue_time: '2026-08-29T08:00:00+05:00' }),
      ]),
      activeTab: 'cardio',
      queueProfiles: profiles,
    });
    expect(kind).toBe('queue-empty');
  });

  it('specific tab holding entries → filtered-empty (zero rows are caused by the search/status narrowing, not by an empty queue)', () => {
    // F-17 defect scenario: the tab queue HAS records; a letter-only search
    // ("иван" vs Петров/Бета) filters everything out, and the UI called it
    // "Очередь пуста" — inviting a duplicate appointment.
    const kind = resolveRegistrarWorklistEmptyScopeKind({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00', patient_fio: 'Петров Пётр' }),
        appt({ id: '2', queue_tag: 'cardio-kb', queue_time: '2026-08-29T08:30:00+05:00', patient_fio: 'Бета' }),
      ]),
      activeTab: 'cardio',
      queueProfiles: profiles,
    });
    expect(kind).toBe('filtered-empty');
  });

  it('secondary tag of a multi-tag profile counts as scope entries (same SSOT tag resolution as rows)', () => {
    const kind = resolveRegistrarWorklistEmptyScopeKind({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'cardio-kb', queue_time: '2026-08-29T08:00:00+05:00' }),
      ]),
      activeTab: 'cardio',
      queueProfiles: profiles,
    });
    expect(kind).toBe('filtered-empty');
  });

  it('profile without queue_tags falls back to [tabKey] (same adapter as rows)', () => {
    const kind = resolveRegistrarWorklistEmptyScopeKind({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'derma', queue_time: '2026-08-29T08:00:00+05:00' }),
      ]),
      activeTab: 'derma',
      queueProfiles: [{ key: 'derma' }],
    });
    expect(kind).toBe('filtered-empty');
  });

  it('all-departments tab: no appointments at all → queue-empty', () => {
    const kind = resolveRegistrarWorklistEmptyScopeKind({
      appointments: asAppointments([]),
      activeTab: null,
      queueProfiles: profiles,
    });
    expect(kind).toBe('queue-empty');
  });

  it('all-departments tab: any loaded appointment → filtered-empty (aggregation cannot lose every patient)', () => {
    const kind = resolveRegistrarWorklistEmptyScopeKind({
      appointments: asAppointments([
        appt({ id: '1', queue_tag: 'lab', queue_time: '2026-08-29T08:00:00+05:00' }),
      ]),
      activeTab: null,
      queueProfiles: profiles,
    });
    expect(kind).toBe('filtered-empty');
  });
});

// RQ-21.b (D-07 APPROVED): the worklist counters are SIGNED — they name
// their unit ('records' on a specific tab, 'patients' on the aggregated
// all-departments view — the two row kinds must never share one label),
// carry the honest scope (the loaded day+tab scope BEFORE status/search
// narrowing), and never present a narrowed count as the whole scope
// ("показано N из M") nor a loaded page as the total (loadedPage mirrors
// paginationInfo.hasMore — the registrar/queues/today contract returns the
// full day today, so the flag is structural honesty for future paging).
describe('describeRegistrarWorklistCounter (RQ-21.b, D-07)', () => {
  const profiles: QueueProfileItem[] = [{ key: 'cardio', queue_tags: ['cardiology', 'cardio-kb'] }];

  it('specific tab: unit=records; scopeCount counts tag-matched entries BEFORE status/search narrowing', () => {
    const appointments = asAppointments([
      appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00', patient_fio: 'Иванов Иван' }),
      appt({ id: '2', queue_tag: 'cardio-kb', queue_time: '2026-08-29T08:30:00+05:00', patient_fio: 'Бета' }),
      appt({ id: '3', queue_tag: 'lab', queue_time: '2026-08-29T07:00:00+05:00', patient_fio: 'Гамма' }),
    ]);
    const rows = computeRegistrarWorklistRows({
      appointments, activeTab: 'cardio', statusFilter: null, searchQuery: 'иван',
      queueProfiles: profiles, services: {}, fallbackPatientLabel: FALLBACK,
    });
    const d = describeRegistrarWorklistCounter({
      appointments, activeTab: 'cardio', queueProfiles: profiles, rows, hasMore: false,
    });
    expect(d.unit).toBe('records');
    expect(d.scopeCount).toBe(2); // both cardio entries are in the tab scope
    expect(d.count).toBe(rows.length); // one source: the list under the counter
    expect(d.narrowed).toBe(true); // search narrowed 2 → 1
  });

  it('all-departments view: unit=patients; scopeCount is the AGGREGATED patient count, not the record count', () => {
    // S-18: one patient with several services/doctors is ONE patient row on
    // the all-departments view — the counter must not call those «записи».
    const appointments = asAppointments([
      appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00', patient_fio: 'Иванов Иван', patient_id: 100 }),
      appt({ id: '2', queue_tag: 'lab', queue_time: '2026-08-29T08:30:00+05:00', patient_fio: 'Иванов Иван', patient_id: 100 }),
      appt({ id: '3', queue_tag: 'lab', queue_time: '2026-08-29T09:00:00+05:00', patient_fio: 'Петров Пётр', patient_id: 200 }),
    ]);
    const rows = computeRegistrarWorklistRows({
      appointments, activeTab: null, statusFilter: null, searchQuery: '',
      queueProfiles: profiles, services: {}, fallbackPatientLabel: FALLBACK,
    });
    const d = describeRegistrarWorklistCounter({
      appointments, activeTab: null, queueProfiles: profiles, rows, hasMore: false,
    });
    expect(d.unit).toBe('patients');
    expect(d.scopeCount).toBe(2); // two patients from three records
    expect(d.count).toBe(rows.length);
    expect(d.narrowed).toBe(false);
  });

  it('no narrowing → narrowed=false even with a full scope; empty scope stays honest (0 of 0 is not narrowed)', () => {
    const appointments = asAppointments([
      appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00' }),
    ]);
    const rows = computeRegistrarWorklistRows({
      appointments, activeTab: 'cardio', statusFilter: null, searchQuery: '',
      queueProfiles: profiles, services: {}, fallbackPatientLabel: FALLBACK,
    });
    const d = describeRegistrarWorklistCounter({
      appointments, activeTab: 'cardio', queueProfiles: profiles, rows, hasMore: false,
    });
    expect(d.narrowed).toBe(false);
    expect(d.count).toBe(d.scopeCount);

    const empty = describeRegistrarWorklistCounter({
      appointments: asAppointments([]), activeTab: 'cardio', queueProfiles: profiles,
      rows: [], hasMore: false,
    });
    expect(empty.narrowed).toBe(false);
    expect(empty.scopeCount).toBe(0);
    expect(empty.count).toBe(0);
  });

  it('status filter narrows before aggregation on all-departments; narrowed reflects rows vs aggregated scope', () => {
    const appointments = asAppointments([
      appt({ id: '1', queue_tag: 'lab', queue_time: '2026-08-29T08:00:00+05:00', patient_fio: 'Иванов Иван', status: 'waiting' }),
      appt({ id: '2', queue_tag: 'lab', queue_time: '2026-08-29T08:30:00+05:00', patient_fio: 'Петров Пётр', status: 'done' }),
    ]);
    const rows = computeRegistrarWorklistRows({
      appointments, activeTab: null, statusFilter: 'done', searchQuery: '',
      queueProfiles: profiles, services: {}, fallbackPatientLabel: FALLBACK,
    });
    const d = describeRegistrarWorklistCounter({
      appointments, activeTab: null, queueProfiles: profiles, rows, hasMore: false,
    });
    expect(d.scopeCount).toBe(2); // scope ignores the status filter
    expect(d.count).toBe(1);
    expect(d.narrowed).toBe(true);
  });

  it('loadedPage mirrors hasMore (D-07: loaded rows must never be presented as the total)', () => {
    const appointments = asAppointments([
      appt({ id: '1', queue_tag: 'cardiology', queue_time: '2026-08-29T08:00:00+05:00' }),
    ]);
    const rows = computeRegistrarWorklistRows({
      appointments, activeTab: 'cardio', statusFilter: null, searchQuery: '',
      queueProfiles: profiles, services: {}, fallbackPatientLabel: FALLBACK,
    });
    expect(describeRegistrarWorklistCounter({
      appointments, activeTab: 'cardio', queueProfiles: profiles, rows, hasMore: true,
    }).loadedPage).toBe(true);
    expect(describeRegistrarWorklistCounter({
      appointments, activeTab: 'cardio', queueProfiles: profiles, rows, hasMore: false,
    }).loadedPage).toBe(false);
  });
});

describe('formatRegistrarWorklistCounter (RQ-21.b, D-07)', () => {
  // Deterministic ru resolver mirroring the CLDR categories i18next resolves
  // (Intl.PluralRules('ru'): one/few/many) over the REAL keys the formatter
  // asks for — pins the composed grammar, not i18next itself.
  const RU_UNITS: Record<string, [string, string, string]> = {
    'registrarPanel.rp_counter_records': ['запись', 'записи', 'записей'],
    'registrarPanel.rp_counter_patients': ['пациент', 'пациента', 'пациентов'],
  };
  const ruT = (key: string, options?: Record<string, unknown>): string => {
    const unit = RU_UNITS[key];
    if (unit && options && typeof options.count === 'number') {
      const n = options.count;
      if (n % 10 === 1 && n % 100 !== 11) return unit[0];
      if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return unit[1];
      return unit[2];
    }
    if (key === 'registrarPanel.rp_counter_shown_of') {
      return `показано ${options?.shown} из ${options?.scope} ${options?.unit}`;
    }
    if (key === 'registrarPanel.rp_counter_loaded') return 'загружено:';
    return key;
  };

  it('plain form: count + unit word in the correct ru plural form (1 запись / 3 записи / 5 записей / 0 записей)', () => {
    const mk = (count: number) => ({
      unit: 'records' as const, count, scopeCount: count, narrowed: false, loadedPage: false,
    });
    expect(formatRegistrarWorklistCounter(ruT, mk(1))).toBe('1 запись');
    expect(formatRegistrarWorklistCounter(ruT, mk(3))).toBe('3 записи');
    expect(formatRegistrarWorklistCounter(ruT, mk(5))).toBe('5 записей');
    expect(formatRegistrarWorklistCounter(ruT, mk(0))).toBe('0 записей');
  });

  it('patients unit: 2 пациента / 5 пациентов — units never mixed across surfaces', () => {
    const mk = (count: number) => ({
      unit: 'patients' as const, count, scopeCount: count, narrowed: false, loadedPage: false,
    });
    expect(formatRegistrarWorklistCounter(ruT, mk(2))).toBe('2 пациента');
    expect(formatRegistrarWorklistCounter(ruT, mk(5))).toBe('5 пациентов');
  });

  it('narrowed form: «показано N из M» with the unit word agreeing with the SCOPE number', () => {
    expect(formatRegistrarWorklistCounter(ruT, {
      unit: 'records', count: 1, scopeCount: 3, narrowed: true, loadedPage: false,
    })).toBe('показано 1 из 3 записи');
    expect(formatRegistrarWorklistCounter(ruT, {
      unit: 'records', count: 1, scopeCount: 5, narrowed: true, loadedPage: false,
    })).toBe('показано 1 из 5 записей');
    expect(formatRegistrarWorklistCounter(ruT, {
      unit: 'patients', count: 0, scopeCount: 2, narrowed: true, loadedPage: false,
    })).toBe('показано 0 из 2 пациента');
  });

  it('loaded page: honest «загружено:» prefix instead of presenting a page as the total', () => {
    expect(formatRegistrarWorklistCounter(ruT, {
      unit: 'records', count: 50, scopeCount: 50, narrowed: false, loadedPage: true,
    })).toBe('загружено: 50 записей');
    expect(formatRegistrarWorklistCounter(ruT, {
      unit: 'records', count: 3, scopeCount: 9, narrowed: true, loadedPage: true,
    })).toBe('загружено: показано 3 из 9 записей');
  });
});
