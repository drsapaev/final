/**
 * RQ-05.b — контракт DTO каталога регистратуры (GET /registrar/services).
 *
 * Цепочка «обязательный врач по DTO-флагу»:
 *   backend _services_doctors.py отдаёт per-service requires_doctor
 *   (F-04, RQ-05) → api/registrar.ts типизирует DTO
 *   (RegistrarCatalogService) → AppointmentWizardV2.validateStep(2)
 *   требует врача по флагу → CartStepV2 рисует селектор врача по флагу.
 *
 * Этот файл пинит ПЕРВЫЕ ДВА звена (источник флага + типизация) —
 * статическими контрактами в духе csrfRecovery.test.ts (чтение
 * исходников). Рантайм-поведение гейта — в
 * components/wizard/__tests__/wizardRequiresDoctor.test.ts.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const backendSerializerPath = path.resolve(
  __dirname,
  '../../../../backend/app/api/v1/endpoints/registrar_integration/_services_doctors.py',
);
const registrarApiPath = path.resolve(__dirname, '../registrar.ts');

// =====================================================================
// 1. Backend: эмиссия флага per-service (F-04)
// =====================================================================

const readSerializer = () => fs.readFileSync(backendSerializerPath, 'utf8');
const serializerServiceDataBlock = () =>
  readSerializer().slice(
    readSerializer().indexOf('service_data = {'),
    readSerializer().indexOf('# [OK] НОВАЯ ЛОГИКА')
  );

describe('RQ-05.b: backend emits requires_doctor per registrar service (F-04)', () => {
  it('service_data includes requires_doctor as bool(...)', () => {
    const block = serializerServiceDataBlock();
    expect(block).toContain('"requires_doctor": bool(');
    expect(block).toContain("getattr(service, 'requires_doctor', False)");
  });

  it('keeps the RQ-05 (F-04) traceability marker', () => {
    expect(readSerializer()).toContain('RQ-05 (F-04)');
  });

  it('emits the fields the frontend DTO type declares', () => {
    const block = serializerServiceDataBlock();
    for (const key of [
      '"id":',
      '"name":',
      '"code":',
      '"price":',
      '"currency":',
      '"duration_minutes":',
      '"category_id":',
      '"doctor_id":',
      '"department_key":',
      '"category_code":',
      '"service_code":',
      '"queue_tag":',
      '"is_consultation":',
      '"requires_doctor":',
      '"group":',
    ]) {
      expect(block).toContain(key);
    }
  });
});

// =====================================================================
// 2. Frontend: типизация DTO по актуальному ответу бэкенда
// =====================================================================

describe('RQ-05.b: api/registrar.ts types the catalog DTO', () => {
  const readApi = () => fs.readFileSync(registrarApiPath, 'utf8');

  it('declares RegistrarCatalogService with required requires_doctor: boolean', () => {
    const source = readApi();
    const block = source.slice(
      source.indexOf('export interface RegistrarCatalogService'),
      source.indexOf('export interface RegistrarServicesResponse')
    );
    expect(block).toContain('requires_doctor: boolean;');
    expect(block).toContain('is_consultation?: boolean;');
    expect(block).toContain('department_key?: string | null;');
  });

  it('types services_by_group as Record<string, RegistrarCatalogService[]>', () => {
    const source = readApi();
    const block = source.slice(
      source.indexOf('export interface RegistrarServicesResponse'),
      source.indexOf('export async function fetchRegistrarServices')
    );
    expect(block).toContain('services_by_group?: Record<string, RegistrarCatalogService[]>');
  });

  it('documents requires_doctor as the mandatory-doctor flag (RQ-05 F-04 traceability)', () => {
    const source = readApi();
    expect(source).toContain('RQ-05');
    expect(source).toContain('F-04');
  });
});
