/**
 * Fix B (profile save) — targeted regression tests.
 *
 * Оригинальный дефект: обычная новая регистрация существующего пациента
 * передавала patient_id как есть, а правки ФИО/адреса/телефона/даты рождения/
 * пола в форме молча терялись; успешный тост показывался без сохранения.
 *
 * Уровни проверки:
 *  1. Unit-тесты чистых хелперов wizardUtils (снимок / diff / верификация).
 *  2. Contract-тесты исходника визарда и backend-схемы PatientUpdate.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { beforeEach, describe, expect, it } from 'vitest';

import {
  buildPatientProfileSnapshot,
  buildPatientProfileUpdate,
  isSavedNameMatching,
} from '../wizardUtils';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const backendSchemaPath = path.resolve(
  __dirname,
  '../../../../../backend/app/schemas/patient.py'
);
const backendServicePath = path.resolve(
  __dirname,
  '../../../../../backend/app/services/patient_service.py'
);
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');

// =====================================================================
// 1. Pure helpers
// =====================================================================

describe('Fix B: buildPatientProfileSnapshot / buildPatientProfileUpdate', () => {
  const card = {
    fio: 'Иванов Иван Иванович',
    phone: '+998 90 123 45 67',
    address: 'ул. Навои, 1',
    birth_date: '1990-05-01',
    sex: 'M',
  };

  it('no update payload when the form matches the selected card', () => {
    const snapshot = buildPatientProfileSnapshot(card);
    const form = { ...card, gender: 'male' };
    expect(buildPatientProfileUpdate(snapshot, form)).toBeNull();
  });

  it('builds update only from actually changed fields', () => {
    const snapshot = buildPatientProfileSnapshot(card);
    const form = {
      fio: 'Иванов Иван Иванович',
      phone: card.phone,
      address: 'новый адрес 42',
      birth_date: '1990-05-01',
      gender: 'male',
    };
    const update = buildPatientProfileUpdate(snapshot, form) as Record<string, unknown>;
    expect(update).toEqual({ address: 'новый адрес 42' });
  });

  it('phone comparison ignores formatting and uses the normalized API phone', () => {
    const snapshot = buildPatientProfileSnapshot(card);
    // Тот же номер в другом форматировании → НЕ изменение
    const samePhone = buildPatientProfileUpdate(
      snapshot,
      { ...card, phone: '+998901234567' },
      { normalizedPhone: '+998901234567' }
    );
    expect(samePhone).toBeNull();
    // Другой номер → изменение с нормализованным значением
    const changed = buildPatientProfileUpdate(
      snapshot,
      { ...card },
      { normalizedPhone: '+998907770011' }
    ) as Record<string, unknown>;
    expect(changed.phone).toBe('+998907770011');
  });

  it('fio edit produces full_name update (never split fields)', () => {
    const snapshot = buildPatientProfileSnapshot(card);
    const update = buildPatientProfileUpdate(
      snapshot,
      { ...card, fio: 'Иванов Иван' }
    ) as Record<string, unknown>;
    expect(update.full_name).toBe('Иванов Иван');
    expect(update.last_name).toBeUndefined();
    expect(update.first_name).toBeUndefined();
  });

  it('returns null without a snapshot (no card selected → no update)', () => {
    expect(
      buildPatientProfileUpdate(null, { fio: 'Кто-то' })
    ).toBeNull();
  });

  it('isSavedNameMatching verifies the re-read server card', () => {
    expect(isSavedNameMatching('Иванов Иван Иванович', 'иванов иван иванович')).toBe(true);
    expect(isSavedNameMatching('Иванов  Иван', 'Иванов Иван')).toBe(true);
    expect(isSavedNameMatching('Петров Пётр', 'Иванов Иван')).toBe(false);
    // Пустые стороны — сверять нечего, ошибкой не считаем
    expect(isSavedNameMatching('', 'Иванов Иван')).toBe(true);
    expect(isSavedNameMatching('Иванов Иван', undefined)).toBe(true);
  });
});

// =====================================================================
// 2. Source contracts (wizard + backend DTO)
// =====================================================================

const extractSourceBlock = (source: string, startMarker: string, endMarker: string) => {
  const start = source.indexOf(startMarker);
  expect(start, `start marker not found: ${startMarker}`).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end, `end marker not found: ${endMarker}`).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('Fix B: wizard profile-save contract', () => {
  let source = '';

  beforeEach(() => {
    source = readWizardSource();
  });

  it('saves changed profile fields of a selected card before cart submit (new mode)', () => {
    const profileSaveBlock = extractSourceBlock(
      source,
      '=== Fix B: явное сохранение правок профиля выбранной карточки (обычный режим) ===',
      'const initialPatientSex = genderToPatientSexForApi'
    );
    expect(profileSaveBlock).toContain('buildPatientProfileUpdate(');
    expect(profileSaveBlock).toContain('await updatePatient(patientId, profileUpdate)');
    // Ошибка сохранения останавливает отправку
    expect(profileSaveBlock).toContain('return;');
    expect(profileSaveBlock).toContain('aw_patient_profile_save_failed');
  });

  it('verifies the re-read card after update (200 alone is not success proof)', () => {
    expect(source).toContain('isSavedNameMatching(');
    expect(source).toContain('aw_patient_profile_verify_failed');
  });

  it('edit-mode attach stops explicitly when the profile update fails', () => {
    const attachBlock = extractSourceBlock(
      source,
      'Updating patient data...',
      "else {\n          // ✅ НОВОЕ: Если в режиме редактирования по QR пациент по телефону не найден,"
    );
    expect(attachBlock).toContain('aw_patient_profile_save_failed');
    expect(attachBlock).not.toContain("logger.warn('⚠️ Failed to update patient:', e);");
  });

  it('keeps profile snapshots in sync with card lifecycle', () => {
    // Снимок создаётся при выборе карточки и инициализации editMode
    expect(source).toContain('selectedCardProfileRef.current = buildPatientProfileSnapshot(');
    expect(source).toContain('editProfileSnapshotRef.current = buildPatientProfileSnapshot(');
    // и сбрасывается при закрытии мастера и очистке формы
    const closeBlock = extractSourceBlock(
      source,
      '✅ ИСПРАВЛЕНО: Сброс состояния мастера при закрытии',
      'Safeguard: Ensure wizardData structure is valid'
    );
    expect(closeBlock).toContain('selectedCardProfileRef.current = null;');
  });

  it('backend PatientUpdate schema accepts full_name and the service normalizes it', () => {
    const schema = fs.readFileSync(backendSchemaPath, 'utf8');
    const updateBlock = extractSourceBlock(schema, 'class PatientUpdate(ORMModel):', 'birth_date: date | None = None');
    expect(updateBlock).toContain('full_name: str | None = Field(None, max_length=255)');

    const service = fs.readFileSync(backendServicePath, 'utf8');
    expect(service).toContain('normalize_patient_name(full_name=str(raw_full_name).strip())');
    // schema-only поле не уходит в CRUD (у ORM full_name — hybrid property)
    expect(service).toContain('update_payload.pop("full_name", None)');
  });
});
