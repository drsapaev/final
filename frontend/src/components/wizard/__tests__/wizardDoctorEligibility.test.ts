/**
 * RQ-08.a — UI-потребление серверной eligibility (родительский критерий
 * RQ-08 «UI не требует alias-списков»).
 *
 * Цепочка: backend-сериализатор каталога отдаёт per-service
 * accepted_specialties — вычисленные ТОЙ ЖЕ функцией
 * (_accepted_specialty_variants_for_department_key, RQ-05.a), что и
 * серверный гейт корзины, → wizardServiceFromCatalogEntry переносит поле
 * ЯВНО (переименование в DTO ломает компиляцию) → filterDoctorsForService
 * применяет серверный набор ПРИОРИТЕТНО. Фронтовая alias-таблица
 * (SPECIALTY_ALIASES, W2-PR2/Codex R10) остаётся только fallback-ом для
 * ответов без серверных данных — живой путь мастера от неё не зависит.
 */
import { describe, expect, it } from 'vitest';

import {
  filterDoctorsForService,
  wizardServiceFromCatalogEntry,
  type WizardCatalogServiceData,
} from '../wizardUtils';

const doctors = [
  { id: 1, specialty: 'dentistry' },
  { id: 2, specialty: 'cardiology' },
  { id: 3, specialty: 'Cardiologist' },
  { id: 4, specialty: '' },
];

describe('RQ-08.a: filterDoctorsForService — серверный набор приоритетен', () => {
  it('применяет accepted_specialties из каталога (dental-семейство RQ-05.a)', () => {
    const service = {
      department_key: 'dental',
      accepted_specialties: ['dental', 'dentist', 'dentistry', 'stomatology'],
    };
    const result = filterDoctorsForService(doctors, service);
    expect(result.map((d) => d.id)).toEqual([1, 4]);
  });

  it('серверный набор побеждает фронтовую таблицу (устойчивость к дрейфу)', () => {
    // Алиаса 'future_family' нет в SPECIALTY_ALIASES — легаси-путь его бы
    // отбросил; серверный список решает.
    const service = {
      department_key: 'future',
      accepted_specialties: ['future_family', 'dentistry'],
    };
    const result = filterDoctorsForService(doctors, service);
    expect(result.map((d) => d.id)).toEqual([1, 4]);
  });

  it('сравнение без учёта регистра (сервер отдаёт lowercase, врач может хранить иначе)', () => {
    const service = {
      department_key: 'cardiology',
      accepted_specialties: ['CARDIOLOGY'],
    };
    const result = filterDoctorsForService(doctors, service);
    expect(result.map((d) => d.id)).toEqual([2, 4]);
  });

  it('врач без специальности остаётся допустимым и на серверном пути', () => {
    const service = {
      department_key: 'lab',
      accepted_specialties: ['lab', 'laboratory'],
    };
    const result = filterDoctorsForService(
      [
        { id: 9, specialty: 'dentistry' },
        { id: 10, specialty: '' },
      ],
      service,
    );
    expect(result.map((d) => d.id)).toEqual([10]);
  });
});

describe('RQ-08.a: fallback и явный null — прежнее поведение/гейт-семантика', () => {
  it('строковый ключ (легаси-вызовы/тесты) — alias-таблица, как раньше', () => {
    const result = filterDoctorsForService(doctors, 'dental');
    // dental → канон dentistry через фронтовую таблицу (W2-PR2/Codex R10)
    expect(result.map((d) => d.id)).toEqual([1, 4]);
  });

  it('accepted_specialties: null — сервер ЯВНО снял проверку → ВСЕ врачи (codex P1 раунд 2)', () => {
    // Пустое поле Service.department_key + связь с отделением: гейт RQ-05.a
    // при accepted is None специальность НЕ проверяет. UI обязан показать
    // всех, а не фильтровать по link-priority department_key.
    const service = { department_key: 'cardiology', accepted_specialties: null };
    expect(filterDoctorsForService(doctors, service).map((d) => d.id)).toEqual([1, 2, 3, 4]);
  });

  it('accepted_specialties отсутствует (undefined, старый бэкенд) — fallback на alias-таблицу', () => {
    const service = { department_key: 'dental' };
    expect(filterDoctorsForService(doctors, service).map((d) => d.id)).toEqual([1, 4]);
  });

  it('пустой accepted_specialties — fallback, а не «не кого не пускать» (defensive)', () => {
    // Сервер при заданном поле не отдаёт пустой набор; пустой массив
    // трактуем как отсутствие данных.
    const service = { department_key: 'dental', accepted_specialties: [] };
    const result = filterDoctorsForService(doctors, service);
    expect(result.map((d) => d.id)).toEqual([1, 4]);
  });

  it('без department_key — все врачи', () => {
    expect(filterDoctorsForService(doctors, {}).map((d) => d.id)).toEqual([1, 2, 3, 4]);
    expect(filterDoctorsForService(doctors, null).map((d) => d.id)).toEqual([1, 2, 3, 4]);
  });
});

describe('RQ-08.a: адаптер переносит accepted_specialties ЯВНО (три состояния без коллапса)', () => {
  it('массив сервера проходит как есть', () => {
    const data: WizardCatalogServiceData = wizardServiceFromCatalogEntry({
      id: 7,
      name: 'dental service',
      requires_doctor: true,
      department_key: 'dental',
      accepted_specialties: ['dentistry', 'dental'],
    });
    expect(data.accepted_specialties).toEqual(['dentistry', 'dental']);
  });

  it('undefined (старый бэкенд) остаётся undefined — НЕ коллапсирует в null (codex P1 раунд 2)', () => {
    const data = wizardServiceFromCatalogEntry({
      id: 9,
      name: 'legacy entry',
      requires_doctor: false,
    });
    expect(data.accepted_specialties).toBeUndefined();
  });

  it('явный null сервера остаётся null (проверка неприменима)', () => {
    const data = wizardServiceFromCatalogEntry({
      id: 10,
      name: 'no department field',
      requires_doctor: true,
      accepted_specialties: null,
    });
    expect(data.accepted_specialties).toBeNull();
  });

  it('не-массив нормализуется в null (грязный DTO не ломает фильтр)', () => {
    const data = wizardServiceFromCatalogEntry({
      id: 8,
      name: 'x',
      requires_doctor: false,
      accepted_specialties: 'garbage' as unknown as string[],
    });
    expect(data.accepted_specialties).toBeNull();
  });
});
