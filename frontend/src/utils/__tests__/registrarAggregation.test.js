import { describe, expect, it } from 'vitest';

import {
  aggregatePatientsForAllDepartments,
  sortRegistrarRowsForPresentation
} from '../registrarAggregation';

const makeAppointment = (overrides = {}) => ({
  id: overrides.id ?? 1,
  patient_id: overrides.patient_id ?? 10,
  patient_fio: overrides.patient_fio ?? 'Тест Пациент',
  patient_birth_year: overrides.patient_birth_year ?? 1990,
  patient_phone: overrides.patient_phone ?? '+998900000000',
  address: overrides.address ?? 'Тестовый адрес',
  visit_id: overrides.visit_id ?? overrides.id ?? 1,
  appointment_id: overrides.appointment_id ?? overrides.id ?? 1,
  queue_entry_id: overrides.queue_entry_id ?? null,
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
