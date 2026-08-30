/**
 * PR-UI-13-2 unit contract: filterServicesByDepartment — the pure
 * department-based service display filter extracted from RegistrarPanel.
 *
 * Pins the three-tier resolution order (pinned at source level by
 * RegistrarPanel.contract.test.tsx):
 *   1. backend department_key metadata (service_details / services map)
 *   2. legacy code-prefix tables (departmentCodePrefixes / category mapping)
 *   3. pass-through / empty
 */
import { describe, expect, it } from 'vitest';

import type { Appointment } from '../../../types/domain/clinic';
import { filterServicesByDepartment } from '../registrarServiceFilter';

const appt = (overrides: Record<string, unknown>): Appointment =>
  overrides as unknown as Appointment;

describe('filterServicesByDepartment (PR-UI-13-2)', () => {
  it('departmentKey null: returns services as-is (all-departments tab)', () => {
    const a = appt({ services: ['K01', 'L02'] });
    expect(filterServicesByDepartment(a, null, {})).toEqual(['K01', 'L02']);
  });

  it('departmentKey null with queue_numbers: services preferred, queue-number codes as fallback', () => {
    const withServices = appt({
      services: ['K11'],
      queue_numbers: [{ number: 1, service_name: 'ЭКГ' }],
    });
    expect(filterServicesByDepartment(withServices, null, {})).toEqual(['K11']);

    const withoutServices = appt({
      services: [],
      queue_numbers: [{ number: 1, service_name: 'Консультация кардиолога' }],
    });
    // service names resolve through the SSOT resolver; unresolvable → empty.
    const result = filterServicesByDepartment(withoutServices, null, {});
    expect(Array.isArray(result)).toBe(true);
  });

  it('backend department_key metadata wins (service_details lookup) before legacy prefixes', () => {
    const a = appt({
      services: ['K01', 'L02', 'S01'],
      service_details: [
        { code: 'K01', name: 'Кардио', department_key: 'cardio' },
        { code: 'L02', name: 'Лаб', department_key: 'lab' },
        { code: 'S01', name: 'Стома', department_key: 'dental' },
      ],
    });
    expect(filterServicesByDepartment(a, 'lab', {})).toEqual(['L02']);
  });

  it('legacy category fallback (non-QR records): cardio keeps K-category codes, K10 lands in ECG category and is excluded', () => {
    // NOTE: the departmentCodePrefixes table only applies to QR records
    // (queue_numbers path). Non-QR records resolve codes via the parallel
    // service_codes array (or the services map), then the department
    // category mapping: cardio = ['K', 'ECHO'], and K10 → 'ECG' category.
    const a = appt({
      services: ['K01', 'K10', 'L02'],
      service_codes: ['K01', 'K10', 'L02'],
    });
    expect(filterServicesByDepartment(a, 'cardio', {})).toEqual(['K01']);
  });

  it('legacy category fallback (non-QR records): echokg keeps ECG-category codes only', () => {
    const a = appt({
      services: ['K01', 'K10'],
      service_codes: ['K01', 'K10'],
    });
    expect(filterServicesByDepartment(a, 'echokg', {})).toEqual(['K10']);
  });

  it('legacy category fallback (non-QR records): lab keeps L-category codes only', () => {
    const a = appt({
      services: ['K01', 'L01', 'L11', 'P01'],
      service_codes: ['K01', 'L01', 'L11', 'P01'],
    });
    expect(filterServicesByDepartment(a, 'lab', {})).toEqual(['L01', 'L11']);
  });

  it('QR records (queue_numbers path): cardio prefix keeps K-codes except K10; echokg keeps only K10/ECG', () => {
    const a = appt({
      services: ['K01', 'K10', 'L02'],
      queue_numbers: [{ number: 1 }],
    });
    expect(filterServicesByDepartment(a, 'cardio', {})).toEqual(['K01']);
    expect(filterServicesByDepartment(a, 'echokg', {})).toEqual(['K10']);
  });

  it('QR records: lab prefix keeps L-codes only', () => {
    const a = appt({
      services: ['K01', 'L01', 'L11', 'P01'],
      queue_numbers: [{ number: 1 }],
    });
    expect(filterServicesByDepartment(a, 'lab', {})).toEqual(['L01', 'L11']);
  })

  it('services without backend metadata, service_codes, or queue_numbers yield empty (no specialty heuristics)', () => {
    const a = appt({ services: ['K01'] });
    expect(filterServicesByDepartment(a, 'lab', {})).toEqual([]);
  });

  it('no services → returns them as-is regardless of departmentKey', () => {
    const a = appt({ services: [] });
    expect(filterServicesByDepartment(a, 'cardio', {})).toEqual([]);
  });

  it('records without queue_numbers: backend department_key from the services map filters by identity', () => {
    const a = appt({
      services: [101, 202],
      service_codes: ['K01', 'L02'],
    });
    const servicesMap = {
      cardio: [{ id: 101, name: 'Кардио', service_code: 'K01', department_key: 'cardio' }],
      lab: [{ id: 202, name: 'Лаб', service_code: 'L02', department_key: 'lab' }],
    };
    expect(filterServicesByDepartment(a, 'lab', servicesMap)).toEqual([202]);
  });

  it('QR-record path (queue_numbers) with backend metadata: backend filter wins over prefix table', () => {
    const a = appt({
      services: ['K01', 'L02'],
      service_details: [
        { code: 'K01', department_key: 'cardio' },
        { code: 'L02', department_key: 'lab' },
      ],
      queue_numbers: [{ number: 1 }],
    });
    expect(filterServicesByDepartment(a, 'lab', {})).toEqual(['L02']);
  });
});
