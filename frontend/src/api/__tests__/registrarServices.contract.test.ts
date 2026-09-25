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
// 2. Frontend: проводка типизированного каталога в мастер (codex P2, PR 3309)
// =====================================================================

const wizardPath = path.resolve(
  __dirname,
  '../../components/wizard/AppointmentWizardV2.tsx',
);
const wizardUtilsPath = path.resolve(
  __dirname,
  '../../components/wizard/wizardUtils.ts',
);

describe('RQ-05.b: wizard consumes the typed catalog (end-to-end linkage)', () => {
  const readWizard = () => fs.readFileSync(wizardPath, 'utf8');
  const loadServicesBlock = () => {
    const source = readWizard();
    return source.slice(
      source.indexOf('const loadServices = useCallback(async () => {'),
      source.indexOf('// ===================== РЕЗОЛВИНГ УСЛУГ (SSOT) =====================')
    );
  };

  it('loads the catalog through the typed wrapper fetchRegistrarServices', () => {
    expect(loadServicesBlock()).toContain('await fetchRegistrarServices()');
  });

  it('maps catalog groups through the typed SSOT adapter', () => {
    expect(loadServicesBlock()).toContain('groupServices.map(wizardServiceFromCatalogEntry)');
  });

  it('transfers requires_doctor EXPLICITLY in the adapter (DTO rename breaks compile, not the gate)', () => {
    expect(fs.readFileSync(wizardUtilsPath, 'utf8'))
      .toContain('requires_doctor: Boolean(entry.requires_doctor)');
  });

  it('drops the untyped ServiceData[] cast in the catalog extraction', () => {
    expect(loadServicesBlock()).not.toContain('as ServiceData[]');
  });

  it('normalizes nullable DTO strings for the wizard shape', () => {
    const utils = fs.readFileSync(wizardUtilsPath, 'utf8');
    expect(utils).toContain('service_code: entry.service_code ?? undefined');
    expect(utils).toContain('department_key: entry.department_key ?? undefined');
  });
});

// =====================================================================
// 3. Frontend: типизация DTO по актуальному ответу бэкенда
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

// =====================================================================
// 4. RQ-08.a: серверная eligibility в каталоге (UI не требует alias-списков)
// =====================================================================

describe('RQ-08.a: backend emits doctor eligibility from the shared policy', () => {
  const readSerializer = () => fs.readFileSync(backendSerializerPath, 'utf8');

  it('imports the canonical eligibility helper shared with the cart gate', () => {
    const source = readSerializer();
    expect(source).toContain('from app.services.registrar_doctor_eligibility import');
    expect(source).toContain('accepted_specialty_variants_for_department_key');
  });

  it('emits per-service accepted_specialties from the department_key', () => {
    const source = readSerializer();
    expect(source).toContain('service_data["accepted_specialties"] =');
    expect(source).toContain('accepted_specialty_variants_for_department_key(');
  });

  it('keeps the RQ-08.a traceability marker', () => {
    expect(readSerializer()).toContain('RQ-08.a');
  });
});

describe('RQ-08.a: frontend consumes the server eligibility set', () => {
  it('declares accepted_specialties on the catalog DTO', () => {
    const source = fs.readFileSync(registrarApiPath, 'utf8');
    const block = source.slice(
      source.indexOf('export interface RegistrarCatalogService'),
      source.indexOf('export interface RegistrarServicesResponse'),
    );
    expect(block).toContain('accepted_specialties?: string[] | null;');
  });

  it('transfers accepted_specialties EXPLICITLY in the SSOT adapter (rename breaks compile)', () => {
    const utils = fs.readFileSync(wizardUtilsPath, 'utf8');
    // codex P1 #3311 раунд 2: три состояния БЕЗ коллапса — перенос через
    // transferAcceptedSpecialties (массив | null | undefined).
    expect(utils).toContain(
      'accepted_specialties: transferAcceptedSpecialties(entry.accepted_specialties)',
    );
    expect(utils).toContain('if (raw === undefined) return undefined;');
  });

  it('treats explicit null as no-check (all doctors), not as legacy fallback', () => {
    const utils = fs.readFileSync(wizardUtilsPath, 'utf8');
    // codex P1 #3311 раунд 2: пустое поле Service.department_key + связь —
    // гейт не проверяет специальность, UI обязан показать всех врачей.
    expect(utils).toContain('if (serverAccepted === null) return all;');
  });

  it('renders eligible services inside each named doctor card without a doctor dropdown', () => {
    const cartPath = path.resolve(
      __dirname,
      '../../components/wizard/CartStepV2.tsx',
    );
    const cart = fs.readFileSync(cartPath, 'utf8');
    expect(cart).toContain('.map((doctor) => {');
    expect(cart).toContain('services: candidateServices.filter((service) => filterDoctorsForService([doctor], service).length > 0)');
    expect(cart).toContain('className="cart-step-v2__doctor-card"');
    expect(cart).toContain('className="cart-step-v2__doctor-name"');
    expect(cart).not.toContain('<select');
  });
});
