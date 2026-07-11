import { describe, expect, it } from 'vitest';

import {
  adaptTimeFields,
  aggregatePatientsForAllDepartments,
  sortRegistrarRowsForPresentation
} from '../registrarAggregation';

const pickOverride = (overrides, key, fallback) => (
  Object.prototype.hasOwnProperty.call(overrides, key) ? overrides[key] : fallback
);

const makeAppointment = (overrides = {}) => ({
  id: overrides.id ?? 1,
  patient_id: overrides.patient_id ?? 10,
  patient_fio: overrides.patient_fio ?? 'Тест Пациент',
  patient_birth_year: overrides.patient_birth_year ?? 1990,
  patient_gender: pickOverride(overrides, 'patient_gender', null),
  gender: pickOverride(overrides, 'gender', overrides.patient_gender ?? null),
  sex: pickOverride(overrides, 'sex', overrides.gender ?? overrides.patient_gender ?? null),
  patient_phone: overrides.patient_phone ?? '+998900000000',
  address: overrides.address ?? 'Тестовый адрес',
  visit_id: pickOverride(overrides, 'visit_id', overrides.id ?? 1),
  appointment_id: pickOverride(overrides, 'appointment_id', overrides.id ?? 1),
  queue_entry_id: overrides.queue_entry_id ?? null,
  queue_id: overrides.queue_id ?? null,
  canonical_record_id: overrides.canonical_record_id,
  visit_type: overrides.visit_type ?? null,
  payment_type: overrides.payment_type ?? null,
  payment_status: overrides.payment_status ?? 'pending',
  cost: overrides.cost ?? 0,
  status: overrides.status ?? 'waiting',
  date: overrides.date ?? '2026-04-15',
  appointment_date: overrides.appointment_date ?? '2026-04-15',
  created_at: overrides.created_at ?? '2026-04-15T10:00:00Z',
  queue_time: overrides.queue_time ?? '2026-04-15T09:45:00+05:00',
  services: overrides.services ?? [],
  service_codes: overrides.service_codes ?? [],
  service_details: overrides.service_details ?? [],
  department: overrides.department ?? 'cardiology',
  doctor_specialty: overrides.doctor_specialty ?? null,
  queue_numbers: overrides.queue_numbers ?? [],
  confirmation_status: overrides.confirmation_status ?? null,
  confirmed_at: overrides.confirmed_at ?? null,
  confirmed_by: overrides.confirmed_by ?? null,
  record_type: overrides.record_type ?? 'visit',
  source: overrides.source ?? 'desk',
  discount_mode: overrides.discount_mode ?? 'none',
  approval_status: overrides.approval_status ?? null,
  available_actions: overrides.available_actions ?? [],
  can_mark_paid: overrides.can_mark_paid ?? false,
  can_start_visit: overrides.can_start_visit ?? false,
  can_cancel: overrides.can_cancel ?? false,
  can_print_ticket: overrides.can_print_ticket ?? false,
  can_complete: overrides.can_complete ?? false,
  aggregated_ids: overrides.aggregated_ids,
});

describe('aggregatePatientsForAllDepartments', () => {
  it('keeps a single registration type when all grouped rows match', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({ id: 1, cost: 0, discount_mode: 'repeat' }),
      makeAppointment({ id: 2, cost: 0, discount_mode: 'repeat' }),
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].discount_mode).toBe('repeat');
    expect(result[0].payment_type).toBe('free');
    expect(result[0].cost).toBe(0);
    expect(result[0].cost_display).toBe('free');
  });

  it('marks grouped rows with mixed registration types as mixed', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({ id: 1, cost: 0, discount_mode: 'repeat' }),
      makeAppointment({ id: 2, cost: 100000, discount_mode: 'none' }),
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].discount_mode).toBe('mixed');
    expect(result[0].visit_type).toBe('mixed');
  });

  it('shows free payment state for approved zero-cost registrations', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({ id: 1, cost: 0, discount_mode: 'benefit' }),
      makeAppointment({ id: 2, cost: 0, discount_mode: 'all_free', approval_status: 'approved' }),
    ]);

    expect(result[0].payment_type).toBe('free');
    expect(result[0].cost).toBe(0);
    expect(result[0].cost_display).toBe('free');
  });

  it('shows approval_pending for pending all-free groups', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({ id: 1, cost: 0, discount_mode: 'all_free', approval_status: 'pending' }),
      makeAppointment({ id: 2, cost: 0, discount_mode: 'all_free', approval_status: null }),
    ]);

    expect(result[0].discount_mode).toBe('all_free');
    expect(result[0].payment_type).toBe('approval_pending');
    expect(result[0].cost_display).toBe('free');
    expect(result[0]).not.toHaveProperty('can_mark_paid');
    expect(result[0]).not.toHaveProperty('can_start_visit');
    expect(result[0]).not.toHaveProperty('can_cancel');
    expect(result[0]).not.toHaveProperty('can_print_ticket');
  });

  it('shows mixed payment for groups with mixed statuses or methods', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({ id: 1, cost: 100000, discount_mode: 'none', payment_status: 'paid', payment_type: 'cash' }),
      makeAppointment({ id: 2, cost: 50000, discount_mode: 'none', payment_status: 'pending', payment_type: null }),
    ]);

    expect(result[0].payment_status).toBe('mixed');
    expect(result[0].payment_type).toBe('mixed_payment');
    expect(result[0].cost).toBe(150000);
    expect(result[0]).not.toHaveProperty('can_mark_paid');
    expect(result[0]).not.toHaveProperty('can_start_visit');
    expect(result[0]).not.toHaveProperty('can_cancel');
    expect(result[0]).not.toHaveProperty('can_print_ticket');
  });

  it('does not invent cash payment type when backend value is absent', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({ id: 1, cost: 100000, payment_status: 'pending', payment_type: null, discount_mode: 'none' }),
    ]);

    expect(result[0].payment_type).toBe('pending_payment');
    expect(result[0].grouped_payment_types).toEqual([]);
    expect(result[0]).not.toHaveProperty('can_mark_paid');
    expect(result[0]).not.toHaveProperty('can_start_visit');
    expect(result[0]).not.toHaveProperty('can_cancel');
    expect(result[0]).not.toHaveProperty('can_print_ticket');
  });

  it('preserves backend command availability only inside grouped records', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({
        id: 1,
        cost: 100000,
        canonical_record_id: 101,
        record_kind: 'visit',
        available_actions: ['mark_paid'],
        can_mark_paid: true,
        can_start_visit: false,
        can_cancel: true,
      }),
      makeAppointment({
        id: 2,
        cost: 50000,
        canonical_record_id: 202,
        record_kind: 'online_queue',
        queue_entry_id: 202,
        available_actions: ['start_visit'],
        can_mark_paid: false,
        can_start_visit: true,
        can_cancel: false,
      }),
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].payment_type).toBe('pending_payment');
    expect(result[0]).not.toHaveProperty('available_actions');
    expect(result[0]).not.toHaveProperty('can_mark_paid');
    expect(result[0]).not.toHaveProperty('can_start_visit');
    expect(result[0]).not.toHaveProperty('can_cancel');
    expect(result[0]).not.toHaveProperty('can_print_ticket');
    expect(result[0]).not.toHaveProperty('can_complete');
    expect(result[0].grouped_records).toMatchObject([
      {
        available_actions: ['mark_paid'],
        can_mark_paid: true,
        can_start_visit: false,
        can_cancel: true,
      },
      {
        available_actions: ['start_visit'],
        can_mark_paid: false,
        can_start_visit: true,
        can_cancel: false,
      },
    ]);
  });

  it('does not synthesize visit or appointment ids from online queue row ids', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({
        id: 900001,
        record_kind: 'online_queue',
        record_type: 'online_queue',
        canonical_record_id: 900001,
        visit_id: null,
        appointment_id: null,
        queue_entry_id: 900001,
        available_actions: ['cancel'],
        can_cancel: true,
      }),
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].visit_id).toBeNull();
    expect(result[0].appointment_id).toBeNull();
    expect(result[0].visit_ids).toEqual([]);
    expect(result[0].appointment_ids).toEqual([]);
    expect(result[0].queue_entry_id).toBe(900001);
    expect(result[0].queue_entry_ids).toEqual([900001]);
    expect(result[0].grouped_record_refs).toEqual([
      { record_kind: 'online_queue', record_id: 900001 },
    ]);
  });

  it('promotes only explicit queue entry identity from queue_numbers', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({
        id: 31,
        record_kind: 'online_queue',
        record_type: 'online_queue',
        canonical_record_id: null,
        visit_id: null,
        appointment_id: null,
        queue_entry_id: null,
        queue_numbers: [
          {
            id: 31,
            queue_id: 31,
            queue_entry_id: 9001,
            number: 4,
          },
        ],
      }),
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].queue_entry_id).toBe(9001);
    expect(result[0].queue_entry_ids).toEqual([9001]);
    expect(result[0].grouped_record_refs).toEqual([
      { record_kind: 'online_queue', record_id: 9001 },
    ]);
  });

  it('does not promote DailyQueue ids into online queue record refs', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({
        id: 31,
        record_kind: 'online_queue',
        record_type: 'online_queue',
        canonical_record_id: null,
        visit_id: null,
        appointment_id: null,
        queue_entry_id: null,
        queue_numbers: [
          {
            id: 31,
            queue_id: 31,
            number: 4,
          },
        ],
      }),
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].queue_entry_id).toBeNull();
    expect(result[0].queue_entry_ids).toEqual([]);
    expect(result[0].grouped_record_refs).toEqual([]);
  });

  it('preserves the earliest queue_time when grouping all departments', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({
        id: 1,
        queue_time: '2026-04-15T09:30:00+05:00',
        created_at: '2026-04-15T09:31:00+05:00',
      }),
      makeAppointment({
        id: 2,
        queue_time: '2026-04-15T09:35:00+05:00',
        created_at: '2026-04-15T09:36:00+05:00',
      }),
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].queue_time).toBe('2026-04-15T09:30:00+05:00');
    expect(result[0].created_at).toBe('2026-04-15T09:31:00+05:00');
  });

  it('preserves service_details for all-departments edit mode identity', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({
        id: 1,
        service_details: [{ service_id: 10, service_code: 'K01', service_name: 'Консультация кардиолога' }],
      }),
      makeAppointment({
        id: 2,
        service_details: [{ service_id: 20, service_code: 'L01', service_name: 'Общий анализ крови' }],
      }),
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].service_details).toEqual([
      { service_id: 10, service_code: 'K01', service_name: 'Консультация кардиолога' },
      { service_id: 20, service_code: 'L01', service_name: 'Общий анализ крови' },
    ]);
  });

  it('preserves patient gender for all-departments edit mode identity', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({
        id: 1,
        patient_id: 13,
        patient_gender: 'F',
        gender: 'F',
        sex: 'F',
        service_details: [{ service_id: 10, service_code: 'K01', service_name: 'Cardio consult' }],
      }),
      makeAppointment({
        id: 2,
        patient_id: 13,
        patient_gender: null,
        gender: null,
        sex: null,
        service_details: [{ service_id: 20, service_code: 'L01', service_name: 'Blood test' }],
      }),
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].patient_gender).toBe('F');
    expect(result[0].gender).toBe('F');
    expect(result[0].sex).toBe('F');
  });

  it('does not merge distinct backend patients with the same displayed name', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({
        id: 1,
        patient_id: 101,
        patient_fio: 'Same Display Name',
        patient_phone: '+998901111111',
        canonical_record_id: 301,
        record_kind: 'visit',
        visit_id: 301,
        appointment_id: null,
        services: ['Cardio consult'],
        service_details: [{ service_id: 10, service_code: 'K01', service_name: 'Cardio consult' }],
      }),
      makeAppointment({
        id: 2,
        patient_id: 202,
        patient_fio: 'Same Display Name',
        patient_phone: '+998902222222',
        canonical_record_id: 402,
        record_kind: 'online_queue',
        record_type: 'online_queue',
        visit_id: null,
        appointment_id: null,
        queue_entry_id: 402,
        services: ['Blood test'],
        service_details: [{ service_id: 20, service_code: 'L01', service_name: 'Blood test' }],
      }),
    ]);

    expect(result).toHaveLength(2);
    expect(result.map((row) => row.patient_id)).toEqual([101, 202]);
    expect(result[0].grouped_record_refs).toEqual([{ record_kind: 'visit', record_id: 301 }]);
    expect(result[1].grouped_record_refs).toEqual([{ record_kind: 'online_queue', record_id: 402 }]);
    expect(result[0].service_details).toEqual([
      { service_id: 10, service_code: 'K01', service_name: 'Cardio consult' },
    ]);
    expect(result[1].service_details).toEqual([
      { service_id: 20, service_code: 'L01', service_name: 'Blood test' },
    ]);
  });
});

describe('sortRegistrarRowsForPresentation', () => {
  it('orders by backend-provided queue_time without mutating row facts', () => {
    const rows = [
      makeAppointment({
        id: 2,
        queue_time: '2026-04-15T09:40:00+05:00',
        status: 'waiting',
        queue_numbers: [{ id: 20, number: 2, status: 'waiting' }],
        available_actions: ['cancel'],
        can_cancel: true,
      }),
      makeAppointment({
        id: 1,
        queue_time: '2026-04-15T09:30:00+05:00',
        status: 'queued',
        queue_numbers: [{ id: 10, number: 1, status: 'queued' }],
        available_actions: ['start_visit'],
        can_start_visit: true,
      }),
    ];
    const originalRows = JSON.parse(JSON.stringify(rows));

    const sorted = sortRegistrarRowsForPresentation(rows);

    expect(sorted.map((row) => row.id)).toEqual([1, 2]);
    expect(rows).toEqual(originalRows);
    expect(sorted[0]).toMatchObject({
      id: 1,
      status: 'queued',
      queue_numbers: [{ id: 10, number: 1, status: 'queued' }],
      available_actions: ['start_visit'],
      can_start_visit: true,
    });
    expect(sorted[1]).toMatchObject({
      id: 2,
      status: 'waiting',
      queue_numbers: [{ id: 20, number: 2, status: 'waiting' }],
      available_actions: ['cancel'],
      can_cancel: true,
    });
  });

  it('falls back to backend created_at when queue_time is missing', () => {
    const sorted = sortRegistrarRowsForPresentation([
      makeAppointment({ id: 3, queue_time: '', created_at: '2026-04-15T09:45:00+05:00' }),
      makeAppointment({ id: 4, queue_time: '', created_at: '2026-04-15T09:15:00+05:00' }),
    ]);

    expect(sorted.map((row) => row.id)).toEqual([4, 3]);
  });

  it('uses id only as a presentation tie-breaker', () => {
    const sorted = sortRegistrarRowsForPresentation([
      makeAppointment({ id: 9, queue_time: '2026-04-15T09:30:00+05:00' }),
      makeAppointment({ id: 7, queue_time: '2026-04-15T09:30:00+05:00' }),
    ]);

    expect(sorted.map((row) => row.id)).toEqual([7, 9]);
  });
});

describe('adaptTimeFields (PR-11)', () => {
  it('passes through all 6 time fields from a flat entry', () => {
    const entry = {
      id: 1,
      created_at: '2026-07-11T09:25:00+00:00',
      queue_time: '2026-07-11T14:30:00+05:00',
      updated_at: '2026-07-11T14:35:00+05:00',
      last_changed_at: '2026-07-11T14:35:00+05:00',
      display_time_kind: 'queue_time',
      timezone: 'Asia/Tashkent',
    };

    const result = adaptTimeFields(entry, { timezone: 'Asia/Tashkent' });

    expect(result.created_at).toBe('2026-07-11T09:25:00+00:00');
    expect(result.queue_time).toBe('2026-07-11T14:30:00+05:00');
    expect(result.updated_at).toBe('2026-07-11T14:35:00+05:00');
    expect(result.last_changed_at).toBe('2026-07-11T14:35:00+05:00');
    expect(result.display_time_kind).toBe('queue_time');
    expect(result.timezone).toBe('Asia/Tashkent');
  });

  it('falls back queue_time to created_at when queue_time is missing', () => {
    const entry = {
      id: 2,
      created_at: '2026-07-11T09:25:00+00:00',
    };

    const result = adaptTimeFields(entry, {});

    expect(result.queue_time).toBe('2026-07-11T09:25:00+00:00');
    expect(result.display_time_kind).toBe('created_at');
  });

  it('uses data.timezone fallback when entry.timezone is missing', () => {
    const entry = { id: 3, created_at: '2026-07-11T09:25:00+00:00' };

    const result = adaptTimeFields(entry, { timezone: 'Asia/Tashkent' });

    expect(result.timezone).toBe('Asia/Tashkent');
  });

  it('falls back to Asia/Tashkent when no timezone is provided anywhere', () => {
    const entry = { id: 4, created_at: '2026-07-11T09:25:00+00:00' };

    const result = adaptTimeFields(entry, {});

    expect(result.timezone).toBe('Asia/Tashkent');
  });

  it('handles entry with nested data wrapper', () => {
    const entry = {
      id: 5,
      data: {
        created_at: '2026-07-11T09:25:00+00:00',
        queue_time: '2026-07-11T14:30:00+05:00',
        updated_at: '2026-07-11T14:35:00+05:00',
      },
    };

    const result = adaptTimeFields(entry, { timezone: 'Asia/Tashkent' });

    expect(result.created_at).toBe('2026-07-11T09:25:00+00:00');
    expect(result.queue_time).toBe('2026-07-11T14:30:00+05:00');
    expect(result.updated_at).toBe('2026-07-11T14:35:00+05:00');
  });

  it('falls back updated_at to last_changed_at and vice versa', () => {
    const entry = {
      id: 6,
      created_at: '2026-07-11T09:25:00+00:00',
      last_changed_at: '2026-07-11T14:35:00+05:00',
    };

    const result = adaptTimeFields(entry, {});

    expect(result.updated_at).toBe('2026-07-11T14:35:00+05:00');
    expect(result.last_changed_at).toBe('2026-07-11T14:35:00+05:00');
  });
});
