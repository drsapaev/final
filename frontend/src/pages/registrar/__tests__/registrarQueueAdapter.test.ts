/**
 * PR-UI-13-1 unit contract: registrarQueueAdapter — the pure SSOT
 * field-adaptation layer (backend queue entry → worklist row).
 *
 * These tests pin the passthrough/normalization rules that previously lived
 * inline in RegistrarPanel.loadAppointments (asserted only indirectly via
 * RegistrarPanel.contract.test.tsx source pins). Behavior contract:
 * - one backend entry = one row (no dedup/aggregation — backend owns facts)
 * - entries without an ID are skipped
 * - display fields: fullEntry.* ?? entry.* ?? defaults
 * - gender triple normalized via normalizePatientGender
 */
import { describe, expect, it } from 'vitest';

import { adaptQueueEntry } from '../registrarQueueAdapter';

const FALLBACK = 'Неизвестный пациент';

const baseQueue = { queue_tag: 'cardio', specialty: 'cardio', specialist_name: 'Кардиология' };
const baseData = { date: '2026-08-29', timezone: 'Asia/Tashkent' };

describe('adaptQueueEntry (PR-UI-13-1)', () => {
  it('skips entries without an id (null result)', () => {
    expect(adaptQueueEntry({ patient_fio: 'X' }, baseQueue, baseData, '2026-08-29', FALLBACK)).toBeNull();
    expect(adaptQueueEntry({ data: { patient_fio: 'Y' } }, baseQueue, baseData, '2026-08-29', FALLBACK)).toBeNull();
  });

  it('unwraps entry.data payload when present', () => {
    const row = adaptQueueEntry(
      { data: { id: 7, patient_fio: 'Тестов Тест', canonical_status: 'waiting' } },
      baseQueue,
      baseData,
      '2026-08-29',
      FALLBACK,
    ) as Record<string, unknown>;
    expect(row.id).toBe(7);
    expect(row.patient_fio).toBe('Тестов Тест');
    expect(row.status).toBe('waiting');
  });

  it('patient display fields use fullEntry → entry fallback chain, then localized fallback label', () => {
    const row = adaptQueueEntry(
      {
        id: 1,
        patient_name: 'Запасной Имя',
        patient_fio: 'Основной Фио',
        birth_year: 1990,
        phone: '+998901234567',
        address: 'ул. Тестовая 1',
      },
      baseQueue,
      baseData,
      '2026-08-29',
      FALLBACK,
    ) as Record<string, unknown>;
    // fullEntry == entry here; fio wins over name
    expect(row.patient_fio).toBe('Основной Фио');
    expect(row.patient_birth_year).toBe(1990);
    expect(row.patient_phone).toBe('+998901234567');
    expect(row.address).toBe('ул. Тестовая 1');
  });

  it('entry-level fallbacks apply when fullEntry lacks display fields', () => {
    const row = adaptQueueEntry(
      { data: { id: 2 }, patient_fio: 'Внешний Фио', patient_phone: '+99890', birth_year: 1985 },
      baseQueue,
      baseData,
      '2026-08-29',
      FALLBACK,
    ) as Record<string, unknown>;
    expect(row.patient_fio).toBe('Внешний Фио');
    expect(row.patient_phone).toBe('+99890');
    expect(row.patient_birth_year).toBe(1985);
  });

  it('falls back to the localized unknown-patient label when no name fields exist', () => {
    const row = adaptQueueEntry({ id: 3 }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(row.patient_fio).toBe(FALLBACK);
    expect(row.patient_phone).toBe('');
    expect(row.patient_birth_year).toBeNull();
  });

  it('gender triple (patient_gender/gender/sex) resolved via normalizePatientGender precedence (patient_gender > patient_sex > gender > sex), passed through verbatim', () => {
    // normalizePatientGender is a passthrough resolver (NOT a translator):
    // values are forwarded exactly as the backend provides them.
    const a = adaptQueueEntry({ id: 4, gender: 'М' }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(a.patient_gender).toBe('М');
    expect(a.gender).toBe('М');
    expect(a.sex).toBe('М');

    const b = adaptQueueEntry({ id: 4, patient_gender: 'male', sex: 'female' }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(b.patient_gender).toBe('male');
    expect(b.gender).toBe('male');
    expect(b.sex).toBe('male');

    const c = adaptQueueEntry({ id: 4, sex: 'female' }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(c.patient_gender).toBe('female');

    const d = adaptQueueEntry({ id: 4 }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(d.patient_gender).toBeNull();
  });

  it('canonical_status precedence: canonical_status > queue_status > status', () => {
    const a = adaptQueueEntry({ id: 5, canonical_status: 'waiting', queue_status: 'called', status: 'done' }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(a.status).toBe('waiting');
    const b = adaptQueueEntry({ id: 6, queue_status: 'called', status: 'done' }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(b.status).toBe('called');
    const c = adaptQueueEntry({ id: 7, status: 'done' }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(c.status).toBe('done');
  });

  it('identity passthrough: canonical_record_id / visit_id / appointment_id / queue_entry_id with entry-level fallback', () => {
    const row = adaptQueueEntry(
      { data: { id: 10, visit_id: 111, appointment_id: 222, queue_entry_id: 333 }, canonical_record_id: 999 },
      baseQueue,
      baseData,
      '2026-08-29',
      FALLBACK,
    ) as Record<string, unknown>;
    expect(row.canonical_record_id).toBe(999);
    expect(row.visit_id).toBe(111);
    expect(row.appointment_id).toBe(222);
    expect(row.queue_entry_id).toBe(333);
    expect(row.record_kind).toBeNull();
    expect(row.source_kind).toBeNull();
  });

  it('array fields default to empty arrays; can_* flags booleanized; scalar defaults applied', () => {
    const row = adaptQueueEntry({ id: 11 }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(row.services).toEqual([]);
    expect(row.service_codes).toEqual([]);
    expect(row.service_details).toEqual([]);
    expect(row.available_actions).toEqual([]);
    expect(row.can_mark_paid).toBe(false);
    expect(row.can_start_visit).toBe(false);
    expect(row.can_cancel).toBe(false);
    expect(row.can_print_ticket).toBe(false);
    expect(row.can_complete).toBe(false);
    expect(row.cost).toBe(0);
    expect(row.source).toBe('desk');
    expect(row.payment_status).toBeNull();
  });

  it('available_actions and can_* flags pass through from backend', () => {
    const row = adaptQueueEntry(
      { id: 12, available_actions: ['mark_paid', 'start_visit'], can_mark_paid: 1, can_cancel: true },
      baseQueue,
      baseData,
      '2026-08-29',
      FALLBACK,
    ) as Record<string, unknown>;
    expect(row.available_actions).toEqual(['mark_paid', 'start_visit']);
    expect(row.can_mark_paid).toBe(true);
    expect(row.can_cancel).toBe(true);
    expect(row.can_start_visit).toBe(false);
  });

  it('queue info block is shaped from entry + queue (number, tag, name, timezone fallback)', () => {
    const row = adaptQueueEntry(
      { id: 13, queue_position: 5 },
      { queue_tag: 'lab', specialist_name: 'Лаборатория' },
      { date: '2026-08-29' }, // no timezone → fallback
      '2026-08-29',
      FALLBACK,
    ) as Record<string, unknown>;
    expect(row.queue_number).toBe(5);
    expect(row.queue_tag).toBe('lab');
    expect(row.queue_name).toBe('Лаборатория');
    expect(row.specialty).toBe('lab');
    expect(row.department).toBe('lab');
    expect(row.queue_numbers).toEqual([
      expect.objectContaining({
        number: 5,
        queue_tag: 'lab',
        queue_name: 'Лаборатория',
        specialty: 'lab',
        timezone: 'Asia/Tashkent',
      }),
    ]);
  });

  it('queue tag/name fall back to queue object fields then queue specialty', () => {
    const row = adaptQueueEntry(
      { id: 14 },
      { specialty: 'derma' },
      baseData,
      '2026-08-29',
      FALLBACK,
    ) as Record<string, unknown>;
    expect(row.queue_tag).toBe('derma');
    expect(row.queue_name).toBe('derma');
  });

  it('queue_number falls back to entry.number when queue_position missing', () => {
    const row = adaptQueueEntry({ id: 15, number: 42 }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(row.queue_number).toBe(42);
  });

  it('date fields fall back to data.date then dateParam', () => {
    const rowA = adaptQueueEntry({ id: 16 }, baseQueue, { date: '2026-08-29' }, '2026-08-30', FALLBACK) as Record<string, unknown>;
    expect(rowA.date).toBe('2026-08-29');
    expect(rowA.appointment_date).toBe('2026-08-29');
    const rowB = adaptQueueEntry({ id: 17 }, baseQueue, {}, '2026-08-30', FALLBACK) as Record<string, unknown>;
    expect(rowB.date).toBe('2026-08-30');
    expect(rowB.appointment_date).toBe('2026-08-30');
  });

  it('session_id and latest_lab_report pass through as opaque values', () => {
    const row = adaptQueueEntry(
      { id: 18, session_id: 'opaque-session-string', latest_lab_report: { status: 'ready' } },
      baseQueue,
      baseData,
      '2026-08-29',
      FALLBACK,
    ) as Record<string, unknown>;
    expect(row.session_id).toBe('opaque-session-string');
    expect(row.latest_lab_report).toEqual({ status: 'ready' });
  });

  it('queue_time falls back to entry.queue_time → fullEntry.queue_time → fullEntry.created_at', () => {
    const a = adaptQueueEntry({ id: 19, queue_time: '08:00' }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(a.queue_time).toBe('08:00');
    const b = adaptQueueEntry({ data: { id: 20, queue_time: '09:30' } }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(b.queue_time).toBe('09:30');
    const c = adaptQueueEntry({ data: { id: 21, created_at: '2026-08-29T07:15:00' } }, baseQueue, baseData, '2026-08-29', FALLBACK) as Record<string, unknown>;
    expect(c.queue_time).toBe('2026-08-29T07:15:00');
  });
});
