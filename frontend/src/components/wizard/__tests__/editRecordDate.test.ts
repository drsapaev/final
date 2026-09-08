/**
 * W2-PR2 — врач и дата записи не теряются.
 *
 * Прежний контракт: edit-сабмит и edit-квота шлы targetDate=getLocalISODate()
 * (правка записи на будущую дату молча переносилась в «сегодня»), а фильтр
 * врачей при пустом совпадении по отделению показывал ВСЕХ врачей (владелец
 * очереди терялся — ADR-001).
 *
 * Эти тесты закрепляют поведение хелперов (поведенческие, не source-пины):
 *   - resolveEditRecordDate: каноническая дата записи из read-модели;
 *   - filterDoctorsForService: профильный фильтр БЕЗ fallback на всех.
 */
import { describe, expect, it } from 'vitest';

import {
  filterDoctorsForService,
  resolveEditRecordDate,
} from '../wizardUtils';

describe('W2-PR2: resolveEditRecordDate', () => {
  it('берёт record_date из read-модели (канонический день записи)', () => {
    expect(
      resolveEditRecordDate({ record_date: '2026-09-15', queue_time: '2026-09-15T09:30:00' })
    ).toBe('2026-09-15');
  });

  it('Codex R9 PR 3118: appointment_date записи предпочтительнее queue_time (adaptTimeFields подставляет created_at)', () => {
    expect(
      resolveEditRecordDate({
        appointment_date: '2026-09-20',
        queue_time: '2026-09-01T10:00:00',
      })
    ).toBe('2026-09-20');
  });

  it('откатывается к дате из queue_time, когда record_date отсутствует', () => {
    expect(resolveEditRecordDate({ queue_time: '2026-09-15T09:30:00' })).toBe('2026-09-15');
  });

  it('игнорирует невалидную record_date и использует fallback queue_time', () => {
    expect(
      resolveEditRecordDate({ record_date: '15/09/2026', queue_time: '2026-09-15T09:30:00' })
    ).toBe('2026-09-15');
  });

  it('возвращает null без данных о дне записи', () => {
    expect(resolveEditRecordDate({})).toBeNull();
    expect(resolveEditRecordDate(null)).toBeNull();
    expect(resolveEditRecordDate(undefined)).toBeNull();
  });

  it('не принимает queue_time без даты', () => {
    expect(resolveEditRecordDate({ queue_time: 'not-a-date' })).toBeNull();
  });
});

describe('W2-PR2: filterDoctorsForService (без fallback на всех)', () => {
  const doctors = [
    { id: 1, specialty: 'cardiology' },
    { id: 2, specialty: 'dermatology' },
    { id: 3, specialty: '' },
  ];

  it('оставляет только врачей профиля услуги', () => {
    const result = filterDoctorsForService(doctors, 'cardiology');
    expect(result.map((d) => d.id)).toEqual([1, 3]);
  });

  it('НЕТ совпадений и нет без-специальностных врачей → пустой список (не «все врачи»)', () => {
    const specialistsOnly = [
      { id: 1, specialty: 'cardiology' },
      { id: 2, specialty: 'dermatology' },
    ];
    // Прежний fallback вернул бы ОБЕИХ; контракт W2-PR2 — пустой список
    expect(filterDoctorsForService(specialistsOnly, 'neurology')).toEqual([]);
  });

  it('врач без специальности остаётся допустимым для любого профиля (правило PR-23, не fallback)', () => {
    // Пустая specialty — per-doctor релаксация из PR-23: матчает любой
    // department_key. Важно: это не возврат «всех врачей» — профильные
    // врачи другого отделения по-прежнему отфильтрованы.
    const result = filterDoctorsForService(doctors, 'neurology');
    expect(result.map((d) => d.id)).toEqual([3]);
  });

  it('без department_key возвращает всех кандидатов (услуга не профильная)', () => {
    expect(filterDoctorsForService(doctors, '')).toHaveLength(3);
    expect(filterDoctorsForService(doctors, null)).toHaveLength(3);
  });

  it('нормализует регистр и пробелы', () => {
    const result = filterDoctorsForService(
      [{ id: 5, specialty: 'Cardiology ' }],
      '  CARDIOLOGY'
    );
    expect(result.map((d) => d.id)).toEqual([5]);
  });

  it('устойчив к null/undefined и мусорным строкам', () => {
    expect(filterDoctorsForService(null, 'cardiology')).toEqual([]);
    expect(filterDoctorsForService([null, { id: 1, specialty: 'cardiology' }], 'cardiology')).toHaveLength(1);
  });
});
