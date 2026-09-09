/**
 * W2-PR1 — buildEditDeltaTargetItems (целевое состояние edit-дельты).
 *
 * Прежний сабмит отправлял в /registrar/cart/edit-delta ТОЛЬКО новые услуги:
 * изменение количества существующей позиции (рост и снижение) вообще не
 * покидало фронтенд, и сохранение завершалось «успехом» без правок услуг.
 * Эти тесты закрепляют классификацию позиций билдером:
 *   - новая услуга → specialist_id из корзины;
 *   - существующая позиция с изменённым количеством → specialist_id=null;
 *   - существующая позиция с неизменённым количеством → не отправляется;
 *   - существующая позиция с НЕИЗВЕСТНЫМ исходным количеством → не
 *     отправляется (нельзя молча превращать неизвестное в снижение).
 */
import { describe, expect, it } from 'vitest';

import {
  buildEditDeltaTargetItems,
  buildEditOriginalServiceIdentity,
  type EditOriginalServiceIdentity,
} from '../wizardUtils';

const servicesData = [
  { id: 1, name: 'Услуга A', service_code: 'LAB-1' },
  { id: 2, name: 'Услуга B', service_code: 'LAB-2' },
];

const identityWithQuantities = (quantities: Record<string, number>): EditOriginalServiceIdentity => {
  const identity = buildEditOriginalServiceIdentity(
    true,
    {
      source: 'desk',
      service_details: Object.entries(quantities).map(([id, quantity]) => ({
        id: Number(id),
        service_id: Number(id),
        quantity,
      })),
    },
    servicesData,
  );
  return identity;
};

describe('W2-PR1: buildEditDeltaTargetItems', () => {
  it('новая услуга уходит в дельту с specialist_id из корзины', () => {
    const identity = identityWithQuantities({ '1': 1 });
    const build = buildEditDeltaTargetItems(
      [{ service_id: 2, quantity: 2, doctor_id: 77 }],
      servicesData,
      identity,
    );
    expect(build.hasNew).toBe(true);
    expect(build.items).toEqual([{ service_id: 2, quantity: 2, specialist_id: 77 }]);
  });

  it('изменённое количество существующей позиции с записью уходит с specialist_id=null и queue_entry_id', () => {
    const identity = identityWithQuantities({ '1': 1 });
    const build = buildEditDeltaTargetItems(
      [{ service_id: 1, quantity: 3, original_queue_id: 42 }],
      servicesData,
      identity,
    );
    expect(build.hasNew).toBe(false);
    expect(build.hasQuantityChange).toBe(true);
    expect(build.items).toEqual([
      { service_id: 1, quantity: 3, specialist_id: null, queue_entry_id: 42 },
    ]);
    expect(build.unroutable).toEqual([]);
  });

  it('Codex R15 PR 3115: одна услуга в двух записях — количества keyed по (запись, услуга)', () => {
    // service_details с одной и той же услугой в ДВУХ записях и разными
    // количествами: карта исходных количеств, keyed только по service_id,
    // оставляла последнее значение — правка первой записи классифицировалась
    // no-op и молча не отправлялась, хотя queue_entry_id адресовал её точно.
    const identity = buildEditOriginalServiceIdentity(
      true,
      {
        source: 'desk',
        service_details: [
          { id: 1, service_id: 1, quantity: 1, queue_entry_id: 11 },
          { id: 1, service_id: 1, quantity: 2, queue_entry_id: 22 },
        ],
      },
      servicesData,
    );
    const build = buildEditDeltaTargetItems(
      [
        { service_id: 1, quantity: 2, original_queue_id: 11 },
        { service_id: 1, quantity: 3, original_queue_id: 22 },
      ],
      servicesData,
      identity,
    );
    // обе правки валидны: первая (1→2) НЕ классифицируется no-op из-за
    // перезаписи количества второй записью, вторая (2→3) адресована своей
    // записью; Genuine no-op был бы только при совпадении с СОБСТВЕННЫМ
    // исходным количеством записи.
    expect(build.hasQuantityChange).toBe(true);
    expect(build.items).toEqual([
      { service_id: 1, quantity: 2, specialist_id: null, queue_entry_id: 11 },
      { service_id: 1, quantity: 3, specialist_id: null, queue_entry_id: 22 },
    ]);
  });

  it('Codex R8 PR 3115: существующая позиция несёт queue_entry_id из original_queue_id', () => {
    const identity = identityWithQuantities({ '1': 2 });
    const build = buildEditDeltaTargetItems(
      [{ service_id: 1, quantity: 4, original_queue_id: 777 }],
      servicesData,
      identity,
    );
    expect(build.items).toEqual([
      { service_id: 1, quantity: 4, specialist_id: null, queue_entry_id: 777 },
    ]);
  });

  it('Codex R9 PR 3118: visit-only позиция (без записи очереди) НЕ уходит в дельту — unroutable', () => {
    // visit-only строка /registrar/queues/today: originalQuantities известны,
    // но queue_entry_id нет. Раньше позиция уходила в edit-delta без
    // идентичности — backend создавал ВТОРОЙ визит с целевым количеством.
    const identity = identityWithQuantities({ '1': 2 });
    const build = buildEditDeltaTargetItems(
      [{ service_id: 1, quantity: 4 }],
      servicesData,
      identity,
    );
    expect(build.items).toEqual([]);
    expect(build.hasQuantityChange).toBe(false);
    expect(build.unroutable).toEqual([{ service_id: 1, name: 'Услуга A' }]);
  });

  it('снижение количества с записью очереди — такая же дельта, как и рост', () => {
    const identity = identityWithQuantities({ '1': 3 });
    const build = buildEditDeltaTargetItems(
      [{ service_id: 1, quantity: 1, original_queue_id: 42 }],
      servicesData,
      identity,
    );
    expect(build.hasQuantityChange).toBe(true);
    expect(build.items).toEqual([
      { service_id: 1, quantity: 1, specialist_id: null, queue_entry_id: 42 },
    ]);
  });

  it('Codex R9 PR 3118: снижение visit-only позиции тоже unroutable (не молча в payload)', () => {
    const identity = identityWithQuantities({ '1': 3 });
    const build = buildEditDeltaTargetItems(
      [{ service_id: 1, quantity: 1 }],
      servicesData,
      identity,
    );
    expect(build.items).toEqual([]);
    expect(build.unroutable).toEqual([{ service_id: 1, name: 'Услуга A' }]);
  });

  it('позиция без изменения количества не отправляется (настоящий no-op)', () => {
    const identity = identityWithQuantities({ '1': 2 });
    const build = buildEditDeltaTargetItems(
      [{ service_id: 1, quantity: 2 }],
      servicesData,
      identity,
    );
    expect(build.items).toEqual([]);
    expect(build.hasQuantityChange).toBe(false);
  });

  it('неизвестное исходное количество не превращается в синтетическое снижение', () => {
    // identity знает только услугу 1; корзина содержит услуги 1 (без
    // изменения) и 2 (существующая по identity, но quantity неизвестен)
    const identity = buildEditOriginalServiceIdentity(
      true,
      {
        source: 'desk',
        service_details: [{ id: 1, service_id: 1, quantity: 2 }],
      },
      servicesData,
    );
    identity.serviceIds.add(2); // услуга 2 «существующая», но её исходного количества нет
    const build = buildEditDeltaTargetItems(
      [
        { service_id: 1, quantity: 2 },
        { service_id: 2, quantity: 5 },
      ],
      servicesData,
      identity,
    );
    expect(build.items).toEqual([]);
  });

  it('услуга вне справочника не сабмитится (зеркало прежнего фильтра)', () => {
    const identity = identityWithQuantities({});
    const build = buildEditDeltaTargetItems(
      [{ service_id: 999, quantity: 1, doctor_id: 7 }],
      servicesData,
      identity,
    );
    expect(build.items).toEqual([]);
  });
});
