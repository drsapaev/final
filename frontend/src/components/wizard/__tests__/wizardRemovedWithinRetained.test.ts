/**
 * REG-FE-084 (follow-up audit 2026-11-02) — удаление ОДНОЙ услуги из
 * СОХРАНЯЕМОЙ записи очереди больше не тихий no-op с успехом.
 *
 * Дефект: read-модель может нести ДВЕ услуги на одной записи очереди
 * (общий original_queue_id). При удалении одной из них
 * buildEditDeltaTargetItems итерирует только ТЕКУЩИЕ позиции (удалённая
 * услуга отсутствует, оставшаяся без изменений → пустой payload), а
 * getRemovedQueueEntryIds видит запись живой → сабмит рапортовал успех,
 * правка не применялась.
 *
 * Фикс: детектор detectRemovedServicesWithinRetainedEntries на исходных
 * (queue, service)-парах из service_details;wizard блокирует сабмит
 * громким отказом. Отмена записи ЦЕЛИКОМ (все услуги записи удалены)
 * остаётся прежней семантикой и детектором НЕ трогается.
 */
import { describe, expect, it } from 'vitest';

import {
  buildEditOriginalServiceIdentity,
  detectRemovedServicesWithinRetainedEntries,
  describeRemovedWithinRetainedRows,
  getRemovedQueueEntryIds,
} from '../wizardUtils';

const servicesData = [
  { id: 1, name: 'Консультация кардиолога', service_code: 'K01' },
  { id: 2, name: 'ЭКГ', service_code: 'K02' },
  { id: 3, name: 'УЗИ', service_code: 'D01' },
] as never[];

// Запись 42 с ДВУМЯ услугами (service_details с quantity — W2-PR1 read-модель).
const initialDataTwoServices = {
  source: 'online',
  service_details: [
    {
      service_id: 1,
      service_name: 'Консультация кардиолога',
      queue_entry_id: 42,
      quantity: 1,
    },
    {
      service_id: 2,
      service_name: 'ЭКГ',
      queue_entry_id: 42,
      quantity: 1,
    },
  ],
};

const identityOf = (initialData: Record<string, unknown>) =>
  buildEditOriginalServiceIdentity(true, initialData, servicesData);

describe('detectRemovedServicesWithinRetainedEntries (REG-FE-084)', () => {
  it('detektiert удаление ОДНОЙ услуги из сохраняемой записи (A удалена, B осталась)', () => {
    const identity = identityOf(initialDataTwoServices);
    // Корзина: только услуга 2 в записи 42.
    const cart = [{ service_id: 2, original_queue_id: 42, quantity: 1 }];

    const removed = detectRemovedServicesWithinRetainedEntries(identity, cart);

    expect(removed).toEqual([
      { queueId: 42, serviceId: 1, name: 'Консультация кардиолога' },
    ]);
  });

  it('НЕ срабатывает, когда обе услуги записи сохранены (обычная правка)', () => {
    const identity = identityOf(initialDataTwoServices);
    const cart = [
      { service_id: 1, original_queue_id: 42, quantity: 1 },
      { service_id: 2, original_queue_id: 42, quantity: 1 },
    ];

    expect(detectRemovedServicesWithinRetainedEntries(identity, cart)).toEqual([]);
  });

  it('НЕ срабатывает при изменении количества (услуга осталась в записи)', () => {
    const identity = identityOf(initialDataTwoServices);
    const cart = [
      { service_id: 1, original_queue_id: 42, quantity: 3 },
      { service_id: 2, original_queue_id: 42, quantity: 1 },
    ];

    expect(detectRemovedServicesWithinRetainedEntries(identity, cart)).toEqual([]);
  });

  it('НЕ срабатывает при отмене записи ЦЕЛИКОМ (оба сервиса удалены) — это семантика getRemovedQueueEntryIds', () => {
    const identity = identityOf(initialDataTwoServices);
    const cart = [{ service_id: 3, original_queue_id: 55, quantity: 1 }];

    expect(detectRemovedServicesWithinRetainedEntries(identity, cart)).toEqual([]);
    // Запись 42 отменяется прежним путём — контракт не меняется.
    expect(getRemovedQueueEntryIds([42], cart)).toEqual([42]);
  });

  it('mixed-типы ID записи не ломают детектор (42 vs "42")', () => {
    const identity = identityOf(initialDataTwoServices);
    // Корзина сохранила услугу 2 записи "42" (строчный id из другого adapter-слоя).
    const cart = [{ service_id: 2, original_queue_id: '42', quantity: 1 }];

    const removed = detectRemovedServicesWithinRetainedEntries(identity, cart);

    expect(removed).toEqual([
      { queueId: 42, serviceId: 1, name: 'Консультация кардиолога' },
    ]);
  });

  it('та же услуга в ДВУХ записях: удаление ЕДИНСТВЕННОЙ услуги записи = отмена записи целиком, не детектор', () => {
    const initialData = {
      source: 'online',
      service_details: [
        { service_id: 1, service_name: 'Консультация', queue_entry_id: 42, quantity: 1 },
        { service_id: 1, service_name: 'Консультация', queue_entry_id: 43, quantity: 1 },
      ],
    };
    const identity = identityOf(initialData);
    // Услуга 1 удалена из записи 42 (в 42 она была ЕДИНСТВЕННОЙ) и осталась в 43.
    const cart = [{ service_id: 1, original_queue_id: 43, quantity: 1 }];

    // Запись 42 ушла из корзины ЦЕЛИКОМ — это семантика отмены записи,
    // детектор её не блокирует.
    expect(detectRemovedServicesWithinRetainedEntries(identity, cart)).toEqual([]);
    expect(getRemovedQueueEntryIds([42, 43], cart)).toEqual([42]);
  });

  it('легаси-запись без queue-идентичности услуги НЕ детектируется (без ложных блокировок)', () => {
    const initialData = {
      source: 'online',
      service_details: [
        { service_id: 1, service_name: 'Консультация', quantity: 1 }, // без queue_entry_id
      ],
    };
    const identity = identityOf(initialData);
    const cart: Array<Record<string, unknown>> = [];

    expect(detectRemovedServicesWithinRetainedEntries(identity, cart)).toEqual([]);
  });

  it('пустая корзина при записи с одной услугой = отмена записи целиком (не детектор)', () => {
    const initialData = {
      source: 'online',
      service_details: [
        { service_id: 1, service_name: 'Консультация', queue_entry_id: 42, quantity: 1 },
      ],
    };
    const identity = identityOf(initialData);

    expect(detectRemovedServicesWithinRetainedEntries(identity, [])).toEqual([]);
    expect(getRemovedQueueEntryIds([42], [])).toEqual([42]);
  });

  it('create-режим (identity пуст) никогда не блокируется', () => {
    const identity = buildEditOriginalServiceIdentity(false, {}, servicesData);
    expect(detectRemovedServicesWithinRetainedEntries(identity, [])).toEqual([]);
  });
});

describe('describeRemovedWithinRetainedRows (REG-FE-084 message)', () => {
  it('называет удалённые услуги и доступный выход', () => {
    const message = describeRemovedWithinRetainedRows([
      { name: 'Консультация кардиолога' },
      { name: 'ЭКГ' },
    ]);

    expect(message).toContain('«Консультация кардиолога», «ЭКГ»');
    expect(message).toContain('недоступно');
    expect(message).toContain('Отмените запись целиком');
  });
});
