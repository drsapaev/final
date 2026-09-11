/**
 * RQ-03 (F-02) — вернуть правильные услуги в мастер.
 *
 * Прежний контракт (дефект F-02, закреплён аудитом E-000):
 *   - getWizardDepartmentFilterKeys(null) → [''], и потребитель фильтровал
 *     каталог по department_key ∈ {''} — на вкладке «Все отделения» скрывалась
 *     каждая услуга, у которой заполнен department_key;
 *   - queue_tags профиля ['ecg','echokg'] сравнивались с department_key
 *     услуги ('cardiology') — ecg-услуга исчезала с вкладки ЭКГ
 *     (тег перепутан с отделением).
 *
 * Новый контракт (поведенческие тесты, SYNTHETIC-данные):
 *   - «Все»/null/'all' → null = каталог не ограничивается;
 *   - теги профиля сравниваются с service.queue_tag (тег↔тег);
 *   - department_key профиля — с service.department_key (отделение↔отделение);
 *   - неизвестная вкладка/пустой профиль — прежнее поведение по ключу;
 *   - легаси-хелпер getWizardDepartmentFilterKeys сохраняет прежний вывод.
 */
import { describe, expect, it } from 'vitest';

import {
  getWizardDepartmentFilterKeys,
  getWizardServiceTabFilter,
} from '../wizardUtils';

// SYNTHETIC-профили по форме DTO /queues/profiles (INITIAL_QUEUE_PROFILES):
// ecg — department_key: null, теги ['ecg','echokg']; cardiology —
// department_key: 'cardiology', теги ['cardio','cardiology','cardiology_common'].
const SYNTHETIC_PROFILES = [
  { key: 'cardiology', queue_tags: ['cardio', 'cardiology', 'cardiology_common'], department_key: 'cardiology' },
  { key: 'ecg', queue_tags: ['ecg', 'echokg'], department_key: null },
  { key: 'dermatology', queue_tags: ['derma', 'dermatology'], department_key: 'dermatology' },
];

describe('RQ-03: вкладка «Все отделения» не ограничивает каталог (F-02 воспроизведение 1)', () => {
  it('null-вкладка возвращает null — фильтрация не выполняется', () => {
    expect(getWizardServiceTabFilter(null, SYNTHETIC_PROFILES)).toBeNull();
  });

  it('пустая строка вкладки возвращает null — прежнее [""] не воспроизводится', () => {
    expect(getWizardServiceTabFilter('', SYNTHETIC_PROFILES)).toBeNull();
    expect(getWizardServiceTabFilter('   ', SYNTHETIC_PROFILES)).toBeNull();
  });

  it('строка "all" также не ограничивает каталог', () => {
    expect(getWizardServiceTabFilter('all', SYNTHETIC_PROFILES)).toBeNull();
    expect(getWizardServiceTabFilter('All', SYNTHETIC_PROFILES)).toBeNull();
  });

  it('без профиля null-вкладка тоже возвращает null (деградированный режим)', () => {
    expect(getWizardServiceTabFilter(null, null)).toBeNull();
  });
});

describe('RQ-03: тег профиля не сравнивается с department_key услуги (F-02 воспроизведение 2)', () => {
  // S-02: профиль ecg+echokg, услуга department=cardiology.
  const ecgFilter = getWizardServiceTabFilter('ecg', SYNTHETIC_PROFILES);

  it('фильтр вкладки ecg берёт теги профиля и не содержит чужих department', () => {
    expect(ecgFilter).toEqual({ tags: ['ecg', 'echokg'], departmentKeys: [] });
  });

  it('ecg-услуга с department_key=cardiology проходит по тегу (тег↔тег)', () => {
    const service = { queue_tag: 'ecg', department_key: 'cardiology' };
    const queueTag = String(service.queue_tag).trim().toLowerCase();
    expect(ecgFilter && ecgFilter.tags.includes(queueTag)).toBe(true);
  });

  it('echokg-услуга (multi-tag профиль) также проходит по тегу', () => {
    const queueTag = 'echokg';
    expect(ecgFilter && ecgFilter.tags.includes(queueTag)).toBe(true);
  });

  it('кардиологическая услуга с queue_tag=cardio не попадает на вкладку ecg', () => {
    const service = { queue_tag: 'cardio', department_key: 'cardiology' };
    const queueTag = String(service.queue_tag).trim().toLowerCase();
    const departmentKey = String(service.department_key).trim().toLowerCase();
    const matchedByTag = Boolean(ecgFilter && ecgFilter.tags.includes(queueTag));
    const matchedByDept = Boolean(
      ecgFilter && ecgFilter.departmentKeys.includes(departmentKey)
    );
    expect(matchedByTag || matchedByDept).toBe(false);
  });

  it('теги и отделение обрабатываются регистронезависимо и с обрезкой', () => {
    const messy = getWizardServiceTabFilter('ECG', [
      { key: 'ecg', queue_tags: ['  ECG ', 'EchoKg'], department_key: null },
    ]);
    expect(messy).toEqual({ tags: ['ecg', 'echokg'], departmentKeys: [] });
  });
});

describe('RQ-03: department_key профиля сравнивается с department_key услуги', () => {
  it('консультация без queue_tag видна на вкладке cardiology по отделению', () => {
    const filter = getWizardServiceTabFilter('cardiology', SYNTHETIC_PROFILES);
    expect(filter).toEqual({
      tags: ['cardio', 'cardiology', 'cardiology_common'],
      departmentKeys: ['cardiology'],
    });
    const consultation = { queue_tag: null, department_key: 'Cardiology ' };
    const departmentKey = String(consultation.department_key).trim().toLowerCase();
    expect(filter && filter.departmentKeys.includes(departmentKey)).toBe(true);
  });

  it('услуга по queue_tag=cardiology_common проходит на вкладку cardiology по тегу', () => {
    const filter = getWizardServiceTabFilter('cardiology', SYNTHETIC_PROFILES);
    expect(filter && filter.tags.includes('cardiology_common')).toBe(true);
  });
});

describe('RQ-03: неизвестная вкладка и пустой профиль (проверка S-02)', () => {
  it('неизвестная вкладка сохраняет прежнее поведение по ключу (E-000: neurology)', () => {
    expect(getWizardServiceTabFilter('neurology', SYNTHETIC_PROFILES)).toEqual({
      tags: [],
      departmentKeys: ['neurology'],
    });
  });

  it('профиль без тегов и без department_key откатывается к ключу вкладки', () => {
    const emptyProfile = [{ key: 'empty-prof', queue_tags: [], department_key: null }];
    expect(getWizardServiceTabFilter('empty-prof', emptyProfile)).toEqual({
      tags: [],
      departmentKeys: ['empty-prof'],
    });
  });

  it('профиль только с department_key (теги пусты) фильтрует по отделению', () => {
    const deptOnly = [{ key: 'lab', queue_tags: [], department_key: 'laboratory' }];
    expect(getWizardServiceTabFilter('lab', deptOnly)).toEqual({
      tags: [],
      departmentKeys: ['laboratory'],
    });
  });

  it('деградированный режим без профилей использует легаси-карту по ключу', () => {
    expect(getWizardServiceTabFilter('cardio', null)).toEqual({
      tags: [],
      departmentKeys: ['cardio'],
    });
    expect(getWizardServiceTabFilter('echokg', null)).toEqual({
      tags: [],
      departmentKeys: ['cardio', 'echokg', 'ecg'],
    });
  });
});

describe('RQ-03: легаси-хелпер getWizardDepartmentFilterKeys сохранён для совместимости', () => {
  it('возвращает прежние значения (не используется мастером после RQ-03)', () => {
    expect(getWizardDepartmentFilterKeys(null)).toEqual(['']);
    expect(getWizardDepartmentFilterKeys('ecg')).toEqual(['cardio', 'echokg', 'ecg']);
    expect(getWizardDepartmentFilterKeys('ecg', SYNTHETIC_PROFILES)).toEqual(['ecg', 'echokg']);
  });
});
