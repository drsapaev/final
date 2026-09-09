import { describe, expect, it } from 'vitest';

import { normalizeServicesFromInitialData } from '../serviceCodeResolver';

describe('normalizeServicesFromInitialData', () => {
  it('uses explicit queue_entry_id instead of DailyQueue identifiers for edit cancellation', () => {
    const [item] = normalizeServicesFromInitialData(
      {
        service_details: [
          {
            id: 5,
            code: 'K01',
            name: 'Cardiology consult',
          },
        ],
        queue_numbers: [
          {
            id: 31,
            queue_id: 31,
            queue_entry_id: 9001,
            service_id: 5,
            service_code: 'K01',
            service_name: 'Cardiology consult',
          },
        ],
      },
      [{ id: 5, service_code: 'K01', name: 'Cardiology consult' }],
    );

    expect(item.original_queue_id).toBe(9001);
  });

  it('does not treat a bare queue_id as an OnlineQueueEntry id', () => {
    const [item] = normalizeServicesFromInitialData(
      {
        service_details: [
          {
            id: 7,
            code: 'D01',
            name: 'Dermatology consult',
          },
        ],
        queue_numbers: [
          {
            id: 44,
            queue_id: 44,
            service_id: 7,
            service_code: 'D01',
            service_name: 'Dermatology consult',
          },
        ],
      },
      [{ id: 7, service_code: 'D01', name: 'Dermatology consult' }],
    );

    expect(item.original_queue_id).toBeNull();
  });
});

// =====================================================================
// Codex R10 PR 3118 (P1): верхнеуровневый queue_entry_id записи очереди
// доходит до нормализованных позиций. У обычной записи (adaptQueueEntry)
// identity живёт ТОЛЬКО на initialData.queue_entry_id: сгенерированные
// queue_numbers не содержат сервисной идентичности, service_details из
// read-модели не копируют id на строки. Без fallback правка количества
// блокировалась как unroutable.
// =====================================================================
describe('normalizeServicesFromInitialData — top-level queue_entry_id fallback (Codex R10 PR 3118)', () => {
  it('прокидывает initialData.queue_entry_id, когда per-service резолв не сработал', () => {
    const [item] = normalizeServicesFromInitialData(
      {
        queue_entry_id: 501,
        service_details: [
          { id: 3, code: 'S01', name: 'Dentistry consult', quantity: 2 },
        ],
        queue_numbers: [{ number: 5, queue_tag: 'dental', status: 'waiting' }],
      },
      [{ id: 3, service_code: 'S01', name: 'Dentistry consult' }],
    );
    expect(item.original_queue_id).toBe(501);
  });

  it('работает и для строкового формата services (legacy)', () => {
    const [item] = normalizeServicesFromInitialData(
      {
        queue_entry_id: 777,
        services: ['S01'],
        queue_numbers: [{ number: 2, queue_tag: 'dental' }],
      },
      [{ id: 3, service_code: 'S01', name: 'Dentistry consult' }],
    );
    expect(item.original_queue_id).toBe(777);
  });

  it('явный per-service id приоритетнее верхнеуровневого', () => {
    const [item] = normalizeServicesFromInitialData(
      {
        queue_entry_id: 501,
        service_details: [
          { id: 3, code: 'S01', name: 'Dentistry consult', queue_entry_id: 9002 },
        ],
      },
      [{ id: 3, service_code: 'S01', name: 'Dentistry consult' }],
    );
    expect(item.original_queue_id).toBe(9002);
  });

  it('visit-only строка (без queue_entry_id) по-прежнему без identity — отказ сохранён', () => {
    const [item] = normalizeServicesFromInitialData(
      {
        record_kind: 'visit',
        service_details: [{ id: 3, code: 'S01', name: 'Dentistry consult' }],
      },
      [{ id: 3, service_code: 'S01', name: 'Dentistry consult' }],
    );
    expect(item.original_queue_id).toBeNull();
  });
});

describe('normalizeServicesFromInitialData — per-entry dedup key (Codex R15 PR 3121)', () => {
  it('сохраняет одну и ту же услугу из ДВУХ записей очереди', () => {
    // Прежний ключ finalizeItems только по услуге выбрасывал вторую detail
    // ещё на нормализации: мастер показывал одну позицию, а «неизменное»
    // сохранение трактовало скрытую запись как удалённую и вызывало каскад
    // отмены её визита и счёта.
    const items = normalizeServicesFromInitialData(
      {
        service_details: [
          {
            id: 5,
            service_id: 5,
            code: 'K01',
            name: 'Cardiology consult',
            quantity: 1,
            queue_entry_id: 9001,
          },
          {
            id: 5,
            service_id: 5,
            code: 'K01',
            name: 'Cardiology consult',
            quantity: 2,
            queue_entry_id: 9002,
          },
        ],
      },
      [{ id: 5, service_code: 'K01', name: 'Cardiology consult' }],
    );

    expect(items).toHaveLength(2);
    expect(items.map((i) => i.original_queue_id).sort()).toEqual([9001, 9002]);
    expect(items.map((i) => i.quantity).sort()).toEqual([1, 2]);
  });

  it('позиции без идентичности записи дедуплицируются по услуге как прежде', () => {
    const items = normalizeServicesFromInitialData(
      {
        service_details: [
          { id: 5, service_id: 5, code: 'K01', name: 'Cardiology consult', quantity: 1 },
          { id: 5, service_id: 5, code: 'K01', name: 'Cardiology consult', quantity: 2 },
        ],
      },
      [{ id: 5, service_code: 'K01', name: 'Cardiology consult' }],
    );

    expect(items).toHaveLength(1);
  });
});
