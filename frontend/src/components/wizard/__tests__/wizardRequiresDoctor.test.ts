/**
 * RQ-05.b — обязательный выбор врача по DTO-флагу requires_doctor.
 *
 * Цепочка: каталог (GET /registrar/services) отдаёт requires_doctor (F-04,
 * RQ-05) → validateStep(2) мастера блокирует шаг, пока у flagged-услуги
 * не выбран врач → CartStepV2 рисует селектор врача по тому же флагу.
 *
 * Хелпер findMissingDoctorItems извлечён в wizardUtils (SSOT, чистая
 * функция) — рантайм-тесты ниже; проводка в validateStep и UI-декларации
 * CartStepV2 пинятся source-контрактами (паттерн wizardCartAtomicity).
 * Типизация DTO и эмиссия флага бэкендом — в
 * api/__tests__/registrarServices.contract.test.ts.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { findMissingDoctorItems } from '../wizardUtils';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const cartStepPath = path.resolve(__dirname, '../CartStepV2.tsx');
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');
const readCartStepSource = () => fs.readFileSync(cartStepPath, 'utf8');

// =====================================================================
// 1. Pure behavior: SSOT-хелпер обязательного врача
// =====================================================================

const svc = (id: number | string, requiresDoctor: boolean) => ({
  id,
  name: `Service ${id}`,
  requires_doctor: requiresDoctor,
});

const cartItem = (serviceId: number | string, doctorId?: number | string | null) => ({
  id: `${serviceId}-${String(doctorId)}`,
  service_id: serviceId,
  doctor_id: doctorId,
});

describe('RQ-05.b: findMissingDoctorItems (pure behavior)', () => {
  it('flags a requires_doctor item without doctor', () => {
    const missing = findMissingDoctorItems(
      [cartItem(5, null)],
      [svc(5, true), svc(7, false)]
    );
    expect(missing).toHaveLength(1);
    expect(missing[0].service_id).toBe(5);
  });

  it('passes a requires_doctor item with doctor selected', () => {
    expect(findMissingDoctorItems([cartItem(5, 42)], [svc(5, true)])).toHaveLength(0);
  });

  it('passes items whose service does not require a doctor', () => {
    expect(findMissingDoctorItems([cartItem(7, undefined)], [svc(7, false)])).toHaveLength(0);
  });

  it('passes items whose service is absent from the catalog (parity with the inline gate)', () => {
    // find() в прежнем инлайн-гейте давал undefined -> флаг не читался ->
    // позиция проходила. Сохраняем ровно эту семантику: каталог ещё не
    // загружен / услуга удалена — шаг не блокируется фантомным требованием.
    expect(findMissingDoctorItems([cartItem(99, undefined)], [svc(5, true)])).toHaveLength(0);
  });

  it('returns empty for an empty cart', () => {
    expect(findMissingDoctorItems([], [svc(5, true)])).toEqual([]);
  });

  it('returns empty when the catalog is empty (parity with the inline gate)', () => {
    expect(findMissingDoctorItems([cartItem(5, null)], [])).toEqual([]);
  });

  it('handles mixed carts: only flagged-doctorless items are missing', () => {
    const cart = [cartItem(5, null), cartItem(5, 42), cartItem(7, null)];
    const missing = findMissingDoctorItems(cart, [svc(5, true), svc(7, false)]);
    expect(missing).toHaveLength(1);
  });
});

// =====================================================================
// 2. Source contract: проводка в validateStep(2)
// =====================================================================

describe('RQ-05.b: wizard validateStep(2) wiring (source contract)', () => {
  it('uses the SSOT helper and keeps the aw_doctors_required message', () => {
    const source = readWizardSource();
    const block = source.slice(
      source.indexOf('const validateStep'),
      source.indexOf('const nextStep = () => {')
    );
    expect(block).toContain('findMissingDoctorItems(');
    expect(block).toContain("newErrors.doctors = t('misc.aw_doctors_required');");
    // Инлайновая копия правила убрана — правило живёт в одном месте.
    expect(block).not.toContain('service?.requires_doctor && !(item');
  });

  it('addToCart pre-nulls doctor for flagged services (explicit missing state)', () => {
    const source = readWizardSource();
    expect(source).toContain('doctor_id: serviceFromData.requires_doctor ? null : undefined');
  });
});

// =====================================================================
// 3. Source contract: CartStepV2 селектор врача по флагу
// =====================================================================

describe('RQ-05.b: CartStepV2 doctor selector per DTO flag (source contract)', () => {
  it('CartService declares requires_doctor and department_key from the DTO', () => {
    const source = readCartStepSource();
    const block = source.slice(
      source.indexOf('export interface CartService'),
      source.indexOf('export interface CartDoctor')
    );
    expect(block).toContain('requires_doctor?: boolean;');
    expect(block).toContain('department_key?: string;');
  });

  it('renders the doctor select for doctor-requiring items and binds doctor_id', () => {
    const source = readCartStepSource();
    expect(source).toContain(
      'const requiresDoctor = Boolean(service?.requires_doctor || service?.is_consultation);'
    );
    expect(source).toContain("value={item.doctor_id || ''}");
    expect(source).toContain("onUpdateItem?.(item.id, 'doctor_id',");
  });
});
