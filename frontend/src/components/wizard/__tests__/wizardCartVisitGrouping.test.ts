import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { groupCartItemsByVisit } from '../wizardUtils';

const departments = new Map<number, string>([
  [1, 'dermatology'],
  [2, 'procedures'],
  [3, 'cardiology'],
  [4, 'cardiology'],
  [5, 'laboratory'],
]);

const resourceQueueTags = new Map<number, string>([
  [1, 'procedures'],
  [2, 'procedures'],
  [3, 'ecg'],
  [4, 'physio'],
]);

const getDepartment = (serviceId: string | number) =>
  departments.get(Number(serviceId)) || 'general';

const getResourceQueueTag = (serviceId: string | number) =>
  resourceQueueTags.get(Number(serviceId)) || null;

describe('registrar cart visit grouping by canonical resource queue', () => {
  it('groups doctorless services with the same queue_tag even when departments differ', () => {
    const visits = groupCartItemsByVisit(
      [
        {
          service_id: 1,
          doctor_id: null,
          quantity: 1,
          visit_date: '2026-09-20',
          visit_time: null,
        },
        {
          service_id: 2,
          doctor_id: null,
          quantity: 1,
          visit_date: '2026-09-20',
          visit_time: null,
        },
      ],
      getDepartment,
      getResourceQueueTag,
    );

    expect(visits).toHaveLength(1);
    expect(visits[0].department).toBe('dermatology');
    expect(visits[0].services.map((service) => service.service_id)).toEqual([1, 2]);
  });

  it('keeps different dates and times as separate visits within one resource queue', () => {
    const visits = groupCartItemsByVisit(
      [
        { service_id: 1, doctor_id: null, visit_date: '2026-09-20', visit_time: null },
        { service_id: 2, doctor_id: null, visit_date: '2026-09-21', visit_time: null },
        { service_id: 2, doctor_id: null, visit_date: '2026-09-20', visit_time: '15:30' },
      ],
      getDepartment,
      getResourceQueueTag,
    );

    expect(visits).toHaveLength(3);
  });

  it('keeps distinct resource queue tags separate even in one department', () => {
    const visits = groupCartItemsByVisit(
      [
        { service_id: 3, doctor_id: null, visit_date: '2026-09-20', visit_time: null },
        { service_id: 4, doctor_id: null, visit_date: '2026-09-20', visit_time: null },
      ],
      getDepartment,
      getResourceQueueTag,
    );

    expect(visits).toHaveLength(2);
  });

  it('preserves department and doctor grouping for services without a resource identity', () => {
    const visits = groupCartItemsByVisit(
      [
        { service_id: 5, doctor_id: 11, visit_date: '2026-09-20', visit_time: null },
        { service_id: 5, doctor_id: 12, visit_date: '2026-09-20', visit_time: null },
      ],
      getDepartment,
      () => null,
    );

    expect(visits).toHaveLength(2);
    expect(visits.map((visit) => visit.doctor_id)).toEqual([11, 12]);
  });
});

describe('registrar edit-mode grouping', () => {
  it('delegates newly added doctorless services to the same queue-aware helper', () => {
    const __dirname = path.dirname(fileURLToPath(import.meta.url));
    const source = fs.readFileSync(
      path.resolve(__dirname, '../AppointmentWizardV2.tsx'),
      'utf8',
    );
    const start = source.indexOf('if (newServicesWithoutDoctor.length > 0) {');
    const end = source.indexOf('// Все новые услуги без специалиста', start);
    const block = source.slice(start, end);

    expect(start).toBeGreaterThanOrEqual(0);
    expect(end).toBeGreaterThan(start);
    expect(block).toContain('groupCartItemsByVisit(');
    expect(block).toContain('getResourceQueueTagByService');
    expect(block).not.toContain('${department}_no_doctor_');
  });
});
