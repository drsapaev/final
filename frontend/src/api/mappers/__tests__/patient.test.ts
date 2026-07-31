/**
 * Tests for PatientDto mapper — validates zod schema + transformation.
 *
 * Per ADR-0018, the mapper is the single validation boundary. These tests
 * verify:
 * 1. Valid DTOs are correctly transformed to domain Patient
 * 2. Invalid DTOs (missing required fields, wrong types) throw ZodError
 * 3. Array mapper skips bad entries without crashing
 */

import { describe, it, expect } from 'vitest';
import { mapPatientDto, mapPatientDtos } from '../patient';
import type { PatientDto } from '../../../types/api';

describe('mapPatientDto', () => {
  const validDto: PatientDto = {
    id: 123,
    last_name: 'Иванов',
    first_name: 'Иван',
    full_name: 'Иванов Иван Иванович',
    middle_name: 'Иванович',
    birth_date: '1990-01-15',
    sex: 'male',
    phone: '+998901234567',
    email: 'ivan@example.com',
    doc_type: 'passport',
    doc_number: 'AB1234567',
    address: 'Tashkent',
    created_at: '2024-01-01T00:00:00Z',
  };

  it('transforms a valid DTO to domain Patient', () => {
    const patient = mapPatientDto(validDto);
    expect(patient.id).toBe(123);
    expect(patient.last_name).toBe('Иванов');
    expect(patient.first_name).toBe('Иван');
    expect(patient.name).toBe('Иванов Иван Иванович');
    expect(patient.birth_date).toBe('1990-01-15');
  });

  it('derives name from first_name + last_name when full_name is null', () => {
    const dto = { ...validDto, full_name: null };
    const patient = mapPatientDto(dto);
    expect(patient.name).toBe('Иван Иванов');
  });

  it('derives name from first_name + last_name when full_name is undefined', () => {
    const { full_name: _, ...dtoWithoutFullName } = validDto;
    const patient = mapPatientDto(dtoWithoutFullName);
    expect(patient.name).toBe('Иван Иванов');
  });

  it('preserves all optional fields', () => {
    const patient = mapPatientDto(validDto);
    expect(patient.middle_name).toBe('Иванович');
    expect(patient.phone).toBe('+998901234567');
    expect(patient.email).toBe('ivan@example.com');
    expect(patient.doc_type).toBe('passport');
    expect(patient.doc_number).toBe('AB1234567');
    expect(patient.address).toBe('Tashkent');
  });

  it('throws ZodError when id is missing', () => {
    const { id: _, ...dtoWithoutId } = validDto;
    expect(() => mapPatientDto(dtoWithoutId)).toThrow();
  });

  it('throws ZodError when id is wrong type (string instead of number)', () => {
    const dto = { ...validDto, id: 'not-a-number' };
    expect(() => mapPatientDto(dto)).toThrow();
  });

  it('throws ZodError when last_name is missing', () => {
    const { last_name: _, ...dtoWithoutLastName } = validDto;
    expect(() => mapPatientDto(dtoWithoutLastName)).toThrow();
  });

  it('throws ZodError when first_name is missing', () => {
    const { first_name: _, ...dtoWithoutFirstName } = validDto;
    expect(() => mapPatientDto(dtoWithoutFirstName)).toThrow();
  });

  it('throws ZodError when created_at is missing', () => {
    const { created_at: _, ...dtoWithoutCreatedAt } = validDto;
    expect(() => mapPatientDto(dtoWithoutCreatedAt)).toThrow();
  });

  it('throws ZodError when dto is null', () => {
    expect(() => mapPatientDto(null)).toThrow();
  });

  it('throws ZodError when dto is undefined', () => {
    expect(() => mapPatientDto(undefined)).toThrow();
  });

  it('throws ZodError when dto is a string', () => {
    expect(() => mapPatientDto('not-an-object')).toThrow();
  });

  it('accepts null for optional fields', () => {
    const dto = {
      ...validDto,
      full_name: null,
      middle_name: null,
      birth_date: null,
      sex: null,
      phone: null,
      email: null,
      doc_type: null,
      doc_number: null,
      address: null,
    };
    const patient = mapPatientDto(dto);
    expect(patient.full_name).toBeNull();
    expect(patient.middle_name).toBeNull();
    expect(patient.birth_date).toBeNull();
  });
});

describe('mapPatientDtos', () => {
  const validDto = {
    id: 1,
    last_name: 'Test',
    first_name: 'Patient',
    created_at: '2024-01-01T00:00:00Z',
  };

  it('transforms an array of valid DTOs', () => {
    const dtos = [validDto, { ...validDto, id: 2 }];
    const patients = mapPatientDtos(dtos);
    expect(patients).toHaveLength(2);
    expect(patients[0].id).toBe(1);
    expect(patients[1].id).toBe(2);
  });

  it('returns empty array for non-array input', () => {
    expect(mapPatientDtos(null)).toEqual([]);
    expect(mapPatientDtos(undefined)).toEqual([]);
    expect(mapPatientDtos({})).toEqual([]);
    expect(mapPatientDtos('string')).toEqual([]);
  });

  it('returns empty array for empty input', () => {
    expect(mapPatientDtos([])).toEqual([]);
  });

  it('skips invalid entries without crashing', () => {
    const dtos = [
      validDto,
      { id: 'wrong-type' }, // invalid — will throw
      { ...validDto, id: 3 }, // valid
      null, // invalid
      { ...validDto, id: 4 }, // valid
    ];
    const patients = mapPatientDtos(dtos);
    expect(patients).toHaveLength(3);
    expect(patients[0].id).toBe(1);
    expect(patients[1].id).toBe(3);
    expect(patients[2].id).toBe(4);
  });
});
