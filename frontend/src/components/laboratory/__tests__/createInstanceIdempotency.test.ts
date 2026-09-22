import '@testing-library/jest-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildCreateInstanceSlotKey,
  clearCreateInstanceIdempotencyKey,
  generateCreateInstanceOperationId,
  peekCreateInstanceIdempotencyKey,
  resolveCreateInstanceIdempotencyKey,
  serializeCreateInstancePayload,
} from '../createInstanceIdempotency';

const APPOINTMENT_PAYLOAD = {
  patient_id: 101,
  appointment_id: 'a-3',
  visit_id: 703,
  template_id: 5,
  service_codes: ['CBC'],
  service_items: [],
};

const SAME_LOGICAL_PAYLOAD = {
  patient_id: 101,
  appointment_id: 'a-3',
  visit_id: 703,
  template_id: 5,
  service_codes: ['CBC'],
  service_items: [],
};

describe('createInstanceIdempotency (PR 3351 review round 9, P1)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('binds a UUID operation key on the first attempt and stores the payload snapshot', () => {
    const key = resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);

    expect(key).toMatch(/^[0-9a-f-]{36}$/i);
    const stored = peekCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    expect(stored).not.toBeNull();
    expect(stored?.key).toBe(key);
    expect(stored?.payload).toBe(serializeCreateInstancePayload(APPOINTMENT_PAYLOAD));
  });

  it('reuses the SAME key for the same payload (lost-response retry, exactly-once contract)', () => {
    const first = resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    // Повтор после потерянного ответа: payload выводится детерминированно из
    // того же приёма/резолюции — снимок совпадает, ключ тот же.
    const second = resolveCreateInstanceIdempotencyKey(SAME_LOGICAL_PAYLOAD);

    expect(second).toBe(first);
  });

  it('survives a module reload: the key is read back from sessionStorage', async () => {
    const first = resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);

    // «Reload»: чистый ре-импорт модуля читает тот же sessionStorage-слот.
    vi.resetModules();
    const reloaded = await import('../createInstanceIdempotency');
    const afterReload = reloaded.resolveCreateInstanceIdempotencyKey(SAME_LOGICAL_PAYLOAD);

    expect(afterReload).toBe(first);
  });

  it('rotates the key when the payload snapshot changes (a different logical operation)', () => {
    const first = resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    const rotated = resolveCreateInstanceIdempotencyKey({
      ...APPOINTMENT_PAYLOAD,
      visit_id: 999,
    });

    expect(rotated).not.toBe(first);
    // Слот теперь связан с новым снимком — повтор нового payload стабилен.
    expect(resolveCreateInstanceIdempotencyKey({ ...APPOINTMENT_PAYLOAD, visit_id: 999 })).toBe(rotated);
  });

  it('clears the slot after a confirmed outcome: the next create is a new operation', () => {
    const first = resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    clearCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);

    expect(peekCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD)).toBeNull();
    const next = resolveCreateInstanceIdempotencyKey(SAME_LOGICAL_PAYLOAD);
    expect(next).not.toBe(first);
  });

  it('keys slots per appointment context: patient B has an independent lifecycle', () => {
    const forA = resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    const forB = resolveCreateInstanceIdempotencyKey({
      ...APPOINTMENT_PAYLOAD,
      patient_id: 102,
      appointment_id: 'a-4',
    });

    expect(forB).not.toBe(forA);
    // Неопределённый исход по A не мешает подтвердить исход по B.
    clearCreateInstanceIdempotencyKey({
      ...APPOINTMENT_PAYLOAD,
      patient_id: 102,
      appointment_id: 'a-4',
    });
    expect(peekCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD)?.key).toBe(forA);
  });

  it('falls back to a patient-scoped slot when the appointment id is absent', () => {
    const withoutAppointment = { ...APPOINTMENT_PAYLOAD, appointment_id: null };
    expect(buildCreateInstanceSlotKey(withoutAppointment)).toBe('patient:101');
    // Тот же payload без appointment-идентичности стабильно переиспользуется.
    const first = resolveCreateInstanceIdempotencyKey(withoutAppointment);
    expect(resolveCreateInstanceIdempotencyKey({ ...withoutAppointment })).toBe(first);
  });

  it('degrades to a fresh key when sessionStorage is corrupted (no crash)', () => {
    const slot = `lab:report-create:idempotency:${buildCreateInstanceSlotKey(APPOINTMENT_PAYLOAD)}`;
    sessionStorage.setItem(slot, '{not json');

    expect(() => resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD)).not.toThrow();
    const key = resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    expect(key).toMatch(/^[0-9a-f-]{36}$/i);
  });

  it('generates unique operation ids', () => {
    const ids = new Set(Array.from({ length: 64 }, () => generateCreateInstanceOperationId()));
    expect(ids.size).toBe(64);
  });
});
