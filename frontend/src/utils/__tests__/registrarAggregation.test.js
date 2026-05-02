import { describe, expect, it } from 'vitest';

import { aggregatePatientsForAllDepartments } from '../registrarAggregation';

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
  });

  it('shows mixed payment for groups with mixed statuses or methods', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({ id: 1, cost: 100000, discount_mode: 'none', payment_status: 'paid', payment_type: 'cash' }),
      makeAppointment({ id: 2, cost: 50000, discount_mode: 'none', payment_status: 'pending', payment_type: null }),
    ]);

    expect(result[0].payment_status).toBe('mixed');
    expect(result[0].payment_type).toBe('mixed_payment');
    expect(result[0].cost).toBe(150000);
  });

  it('does not invent cash payment type when backend value is absent', () => {
    const result = aggregatePatientsForAllDepartments([
      makeAppointment({ id: 1, cost: 100000, payment_status: 'pending', payment_type: null, discount_mode: 'none' }),
    ]);

    expect(result[0].payment_type).toBe('pending_payment');
    expect(result[0].grouped_payment_types).toEqual([]);
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
