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

// CodeQL #1315 (round 10): слот обязан хранить ТОЛЬКО односторонний digest.
// Подстроки payload ( подчёркивания / верхний регистр / кириллица ) не могут
// встретиться ни в hex-digest, ни в 'sha256:'/'fnv1a:'-префиксе, ни в UUID.
const RAW_SLOT = () => window.sessionStorage.getItem(
  `lab:report-create:idempotency:${buildCreateInstanceSlotKey(APPOINTMENT_PAYLOAD)}`,
);

describe('createInstanceIdempotency (PR 3351 review round 9, P1)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('binds a UUID operation key on the first attempt and stores the payload digest', async () => {
    const key = await resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);

    expect(key).toMatch(/^[0-9a-f-]{36}$/i);
    const stored = peekCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    expect(stored).not.toBeNull();
    expect(stored?.key).toBe(key);
    // Digest, не raw payload: sha256 (WebCrypto) или fnv1a (не-secure fallback).
    expect(stored?.payloadDigest).toMatch(/^(sha256:[0-9a-f]{64}|fnv1a:[0-9a-f]{16}:[0-9a-f]+)$/);
    // Digest детерминирован: тот же payload → тот же digest.
    const again = peekCreateInstanceIdempotencyKey(SAME_LOGICAL_PAYLOAD);
    expect(again?.payloadDigest).toBe(stored?.payloadDigest);
  });

  it('reuses the SAME key for the same payload (lost-response retry, exactly-once contract)', async () => {
    const first = await resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    // Повтор после потерянного ответа: payload выводится детерминированно из
    // того же приёма/резолюции — digest совпадает, ключ тот же.
    const second = await resolveCreateInstanceIdempotencyKey(SAME_LOGICAL_PAYLOAD);

    expect(second).toBe(first);
  });

  it('survives a module reload: the key is read back from sessionStorage', async () => {
    const first = await resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);

    // «Reload»: чистый ре-импорт модуля читает тот же sessionStorage-слот.
    vi.resetModules();
    const reloaded = await import('../createInstanceIdempotency');
    const afterReload = await reloaded.resolveCreateInstanceIdempotencyKey(SAME_LOGICAL_PAYLOAD);

    expect(afterReload).toBe(first);
  });

  it('rotates the key when the payload digest changes (a different logical operation)', async () => {
    const first = await resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    const rotated = await resolveCreateInstanceIdempotencyKey({
      ...APPOINTMENT_PAYLOAD,
      visit_id: 999,
    });

    expect(rotated).not.toBe(first);
    // Слот теперь связан с новым digest — повтор нового payload стабилен.
    expect(await resolveCreateInstanceIdempotencyKey({ ...APPOINTMENT_PAYLOAD, visit_id: 999 })).toBe(rotated);
  });

  it('clears the slot after a confirmed outcome: the next create is a new operation', async () => {
    const first = await resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    clearCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);

    expect(peekCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD)).toBeNull();
    const next = await resolveCreateInstanceIdempotencyKey(SAME_LOGICAL_PAYLOAD);
    expect(next).not.toBe(first);
  });

  it('keys slots per appointment context: patient B has an independent lifecycle', async () => {
    const forA = await resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);
    const forB = await resolveCreateInstanceIdempotencyKey({
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

  it('falls back to a patient-scoped slot when the appointment id is absent', async () => {
    const withoutAppointment = { ...APPOINTMENT_PAYLOAD, appointment_id: null };
    expect(buildCreateInstanceSlotKey(withoutAppointment)).toBe('patient:101');
    // Тот же payload без appointment-идентичности стабильно переиспользуется.
    const first = await resolveCreateInstanceIdempotencyKey(withoutAppointment);
    expect(await resolveCreateInstanceIdempotencyKey({ ...withoutAppointment })).toBe(first);
  });

  it('degrades to a fresh key when sessionStorage is corrupted (no crash)', async () => {
    const slot = `lab:report-create:idempotency:${buildCreateInstanceSlotKey(APPOINTMENT_PAYLOAD)}`;
    sessionStorage.setItem(slot, '{not json');

    await expect(resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD)).resolves.toMatch(/^[0-9a-f-]{36}$/i);
  });

  it('generates unique operation ids', () => {
    const ids = new Set(Array.from({ length: 64 }, () => generateCreateInstanceOperationId()));
    expect(ids.size).toBe(64);
  });

  it('never stores the serialized payload in sessionStorage (CodeQL #1315 clear-text PHI, review round 10)', async () => {
    // Round 10: CodeQL js/clear-text-storage-of-sensitive-data пометил
    // raw-снимок payload (ФЛИ: patient_id, appointment_id, клинические поля)
    // в sessionStorage. Слот хранит только { key, payloadDigest } — ни одна
    // подстрока сериализованного payload попасть в storage не может.
    await resolveCreateInstanceIdempotencyKey(APPOINTMENT_PAYLOAD);

    const raw = RAW_SLOT();
    expect(raw).not.toBeNull();
    const record = JSON.parse(raw as string) as Record<string, unknown>;
    expect(Object.keys(record).sort()).toEqual(['key', 'payloadDigest']);
    // Ключевые маркеры payload: подчёркивания/верхний регистр невозможны
    // в digest-hex и UUID, «CBC» и «a-3» — контент-маркеры payload.
    expect(raw).not.toContain('patient_id');
    expect(raw).not.toContain('appointment_id');
    expect(raw).not.toContain('visit_id');
    expect(raw).not.toContain('service_codes');
    expect(raw).not.toContain('service_items');
    expect(raw).not.toContain('CBC');
    expect(raw).not.toContain(serializeCreateInstancePayload(APPOINTMENT_PAYLOAD));
  });
});
