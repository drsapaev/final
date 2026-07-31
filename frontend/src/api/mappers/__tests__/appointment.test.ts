/**
 * Tests for AppointmentDto mapper — validates zod schema + transformation.
 */

import { describe, it, expect } from 'vitest';
import { mapAppointmentDto, mapAppointmentDtos } from '../appointment';

describe('mapAppointmentDto', () => {
  const validDto = {
    id: 1,
    patient_id: 100,
    doctor_id: 50,
    department: 'cardiology',
    appointment_date: '2024-01-15',
    appointment_time: '10:00',
    notes: 'Regular checkup',
    status: 'scheduled',
    visit_type: 'paid',
    payment_type: 'cash',
    services: ['consultation', 'ecg'],
    payment_amount: 150000,
    payment_currency: 'UZS',
    created_at: '2024-01-01T00:00:00Z',
  };

  it('transforms a valid DTO to domain Appointment', () => {
    const appt = mapAppointmentDto(validDto);
    expect(appt.id).toBe(1);
    expect(appt.patient_id).toBe(100);
    expect(appt.status).toBe('scheduled');
  });

  it('normalizes services string[] to Array<{code, name}>', () => {
    const appt = mapAppointmentDto(validDto);
    expect(appt.services).toEqual([
      { code: 'consultation', name: 'consultation' },
      { code: 'ecg', name: 'ecg' },
    ]);
    expect(appt.service_codes).toEqual(['consultation', 'ecg']);
  });

  it('handles null services', () => {
    const dto = { ...validDto, services: null };
    const appt = mapAppointmentDto(dto);
    expect(appt.services).toEqual([]);
    expect(appt.service_codes).toEqual([]);
  });

  it('handles undefined services', () => {
    const { services: _, ...dtoWithoutServices } = validDto;
    const appt = mapAppointmentDto(dtoWithoutServices);
    expect(appt.services).toEqual([]);
  });

  it('throws ZodError when id is missing', () => {
    const { id: _, ...dtoWithoutId } = validDto;
    expect(() => mapAppointmentDto(dtoWithoutId)).toThrow();
  });

  it('throws ZodError when patient_id is missing', () => {
    const { patient_id: _, ...dtoWithoutPatientId } = validDto;
    expect(() => mapAppointmentDto(dtoWithoutPatientId)).toThrow();
  });

  it('throws ZodError when appointment_date is missing', () => {
    const { appointment_date: _, ...dtoWithoutDate } = validDto;
    expect(() => mapAppointmentDto(dtoWithoutDate)).toThrow();
  });

  it('throws ZodError when status is missing', () => {
    const { status: _, ...dtoWithoutStatus } = validDto;
    expect(() => mapAppointmentDto(dtoWithoutStatus)).toThrow();
  });

  it('throws ZodError when created_at is missing', () => {
    const { created_at: _, ...dtoWithoutCreatedAt } = validDto;
    expect(() => mapAppointmentDto(dtoWithoutCreatedAt)).toThrow();
  });

  it('throws ZodError when dto is null', () => {
    expect(() => mapAppointmentDto(null)).toThrow();
  });

  it('throws ZodError when dto is a string', () => {
    expect(() => mapAppointmentDto('not-an-object')).toThrow();
  });
});

describe('mapAppointmentDtos', () => {
  const validDto = {
    id: 1,
    patient_id: 100,
    appointment_date: '2024-01-15',
    status: 'scheduled',
    visit_type: 'paid',
    payment_type: 'cash',
    payment_currency: 'UZS',
    created_at: '2024-01-01T00:00:00Z',
  };

  it('transforms an array of valid DTOs', () => {
    const dtos = [validDto, { ...validDto, id: 2 }];
    const appts = mapAppointmentDtos(dtos);
    expect(appts).toHaveLength(2);
  });

  it('returns empty array for non-array input', () => {
    expect(mapAppointmentDtos(null)).toEqual([]);
    expect(mapAppointmentDtos({})).toEqual([]);
  });

  it('skips invalid entries', () => {
    const dtos = [
      validDto,
      { id: 'wrong' },
      { ...validDto, id: 3 },
      null,
    ];
    const appts = mapAppointmentDtos(dtos);
    expect(appts).toHaveLength(2);
    expect(appts[0].id).toBe(1);
    expect(appts[1].id).toBe(3);
  });
});
