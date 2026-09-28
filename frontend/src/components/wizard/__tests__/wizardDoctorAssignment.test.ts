import { describe, expect, it } from 'vitest';

import {
  collectDoctorAssignmentGaps,
  filterDoctorsForService,
  groupCartItemsByVisit,
} from '../wizardUtils';

/**
 * Workstream A (registrar doctor-services plan, Tasks 3–4):
 * точное назначение услуги врачу и единая врачебная группировка корзины.
 */

const cardiologistA = { id: 7, specialty: 'cardiology', active: true };
const cardiologistB = { id: 8, specialty: 'cardiology', active: true };
const dentist = { id: 9, specialty: 'dentistry', active: true };
const roster = [cardiologistA, cardiologistB, dentist];

describe('filterDoctorsForService: explicit Service.doctor_id pin', () => {
  it('offers a pinned service only on the assigned doctor card', () => {
    const service = {
      department_key: 'cardiology',
      accepted_specialties: ['cardiology', 'cardio', 'cardiologist'],
      doctor_id: 8,
    };
    const result = filterDoctorsForService(roster, service);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(8);
  });

  it('never falls back to a same-specialty colleague when the pinned doctor is absent', () => {
    const service = {
      department_key: 'cardiology',
      accepted_specialties: ['cardiology', 'cardio', 'cardiologist'],
      doctor_id: 999,
    };
    expect(filterDoctorsForService(roster, service)).toEqual([]);
  });

  it('hides a pinned service whose doctor fails specialty eligibility (config error, not a colleague card)', () => {
    const service = {
      department_key: 'cardiology',
      accepted_specialties: ['cardiology', 'cardio', 'cardiologist'],
      doctor_id: 9, // dentist
    };
    expect(filterDoctorsForService(roster, service)).toEqual([]);
  });

  it('keeps the unpinned specialty behavior untouched', () => {
    const service = {
      department_key: 'cardiology',
      accepted_specialties: ['cardiology', 'cardio', 'cardiologist'],
      doctor_id: null,
    };
    const result = filterDoctorsForService(roster, service);
    expect(result.map((d) => d.id)).toEqual([7, 8]);
  });
});

describe('collectDoctorAssignmentGaps: admin instruction state', () => {
  it('reports a pinned service whose doctor is missing from the roster', () => {
    const gaps = collectDoctorAssignmentGaps(
      [
        {
          id: 10,
          name: 'ЭхоКГ закреплённая',
          service_code: 'K11',
          doctor_id: 999,
          department_key: 'cardiology',
          accepted_specialties: ['cardiology'],
        },
      ],
      roster,
    );
    expect(gaps).toHaveLength(1);
    expect(gaps[0].reason).toBe('doctor_missing');
    expect(gaps[0].pinnedDoctorId).toBe(999);
    expect(gaps[0].serviceName).toBe('ЭхоКГ закреплённая');
  });

  it('reports a pinned service whose doctor fails specialty eligibility', () => {
    const gaps = collectDoctorAssignmentGaps(
      [
        {
          id: 11,
          name: 'Кардио-услуга у стоматолога',
          service_code: 'K12',
          doctor_id: 9,
          department_key: 'cardiology',
          accepted_specialties: ['cardiology'],
        },
      ],
      roster,
    );
    expect(gaps).toHaveLength(1);
    expect(gaps[0].reason).toBe('specialty_mismatch');
  });

  it('produces no gaps for a healthy pin and unpinned services', () => {
    expect(
      collectDoctorAssignmentGaps(
        [
          {
            id: 12,
            name: 'ЭхоКГ кардиолога A',
            service_code: 'K11',
            doctor_id: 7,
            department_key: 'cardiology',
            accepted_specialties: ['cardiology'],
          },
          {
            id: 13,
            name: 'Обычная консультация',
            service_code: 'K01',
            doctor_id: null,
            department_key: 'cardiology',
            accepted_specialties: ['cardiology'],
          },
        ],
        roster,
      ),
    ).toEqual([]);
  });
});

describe('groupCartItemsByVisit: one visit per doctor booking', () => {
  const departments = new Map<number, string>([
    [1, 'dermatology'],
    [2, 'procedures'],
  ]);
  const getDepartment = (serviceId: string | number) =>
    departments.get(Number(serviceId)) || 'general';

  it('keeps same-doctor services from different departments in ONE visit', () => {
    const visits = groupCartItemsByVisit(
      [
        { service_id: 1, doctor_id: 11, visit_date: '2026-09-28', visit_time: null },
        { service_id: 2, doctor_id: 11, visit_date: '2026-09-28', visit_time: null },
      ],
      getDepartment,
      () => null,
    );

    expect(visits).toHaveLength(1);
    expect(visits[0].doctor_id).toBe(11);
    expect(visits[0].services.map((s) => s.service_id)).toEqual([1, 2]);
  });

  it('still splits different doctors and different times into separate visits', () => {
    const visits = groupCartItemsByVisit(
      [
        { service_id: 1, doctor_id: 11, visit_date: '2026-09-28', visit_time: null },
        { service_id: 1, doctor_id: 12, visit_date: '2026-09-28', visit_time: null },
        { service_id: 2, doctor_id: 11, visit_date: '2026-09-28', visit_time: '15:30' },
      ],
      getDepartment,
      () => null,
    );

    expect(visits).toHaveLength(3);
    const identity = visits
      .map((v) => `${v.doctor_id}|${v.visit_time ?? ''}`)
      .sort();
    expect(identity).toEqual(['11|', '11|15:30', '12|'].sort());
  });

  it('keeps resource-queue grouping for doctorless services unchanged', () => {
    const visits = groupCartItemsByVisit(
      [
        { service_id: 3, doctor_id: null, visit_date: '2026-09-28', visit_time: null },
        { service_id: 4, doctor_id: null, visit_date: '2026-09-28', visit_time: null },
      ],
      () => 'cardiology',
      (serviceId: string | number) => (Number(serviceId) === 3 ? 'ecg' : 'lab'),
    );

    expect(visits).toHaveLength(2);
    expect(visits.every((v) => v.doctor_id == null)).toBe(true);
  });
});
