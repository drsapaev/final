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
    fio: 'SYNTHETIC-Тестов Тест Тестович',
    phone: '+998 00 000 00 01',
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
      fio: 'SYNTHETIC-Тестов Тест Тестович',
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
      { ...card, phone: '+998000000001' },
      { normalizedPhone: '+998000000001' }
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
      { ...card, fio: 'SYNTHETIC-Тестов Тест' }
    ) as Record<string, unknown>;
    expect(update.full_name).toBe('SYNTHETIC-Тестов Тест');
    expect(update.last_name).toBeUndefined();
    expect(update.first_name).toBeUndefined();
  });

  it('clearing the phone emits phone: null (Codex R1 P1 regression)', () => {
    // Прежний баг: truthiness-фильтр выбрасывал phone из payload при очистке,
    // и старый номер молча оставался в карточке после успешного PUT.
    const snapshot = buildPatientProfileSnapshot(card);
    const cleared = buildPatientProfileUpdate(
      snapshot,
      { ...card, phone: '' },
      { normalizedPhone: '' }
    ) as Record<string, unknown>;
    expect(cleared.phone).toBeNull();
  });

  it('clearing an optional birth date emits birth_date: null, not empty string (Codex R1 P2 regression)', () => {
    // Прежний баг: birth_date: '' отвергается Pydantic (date | None) с 422
    // и блокирует отправку визита с прочими правками профиля.
    const snapshot = buildPatientProfileSnapshot(card);
    const cleared = buildPatientProfileUpdate(
      snapshot,
      { ...card, birth_date: '' }
    ) as Record<string, unknown>;
    expect(cleared.birth_date).toBeNull();
    // Непустая дата по-прежнему уходит строкой
    const changed = buildPatientProfileUpdate(
      snapshot,
      { ...card, birth_date: '1991-06-02' }
    ) as Record<string, unknown>;
    expect(changed.birth_date).toBe('1991-06-02');
  });

  it('returns null without a snapshot (no card selected → no update)', () => {
    expect(
      buildPatientProfileUpdate(null, { fio: 'Кто-то' })
    ).toBeNull();
  });

  it('isSavedNameMatching verifies the re-read server card', () => {
    expect(isSavedNameMatching('SYNTHETIC-Тестов Тест', 'synthetic-тестов тест')).toBe(true);
    expect(isSavedNameMatching('SYNTHETIC-Тестов  Тест', 'SYNTHETIC-Тестов Тест')).toBe(true);
    expect(isSavedNameMatching('SYNTHETIC-Чужой', 'SYNTHETIC-Тестов Тест')).toBe(false);
    // Пустые стороны — сверять нечего, ошибкой не считаем
    expect(isSavedNameMatching('', 'SYNTHETIC-Тестов Тест')).toBe(true);
    expect(isSavedNameMatching('SYNTHETIC-Тестов Тест', undefined)).toBe(true);
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

  it('keeps profile snapshots and the retained card ID in sync with card lifecycle', () => {
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

    // Codex R3 PR 3090 (P1): ID выбранной карточки живёт тем же жизненным циклом —
    // устанавливается в selectPatient, сбрасывается при закрытии и «Очистить»
    expect(source).toContain('selectedPatientCardIdRef.current = patient.id ?? null;');
    expect(closeBlock).toContain('selectedPatientCardIdRef.current = null;');
    const clearDraftBlock = extractSourceBlock(
      source,
      'const clearDraft = () => {',
      "toast.success(t('misc.aw_form_cleared'))"
    );
    expect(clearDraftBlock).toContain('selectedPatientCardIdRef.current = null;');
  });

  it('submit targets the retained selected card BEFORE any new-patient creation (Codex R3 PR 3090 P1 regression)', () => {
    // Прежний баг: правка ФИО очищала wizardData.patient.id, сабмит уходил в
    // ветку создания и плодил дубликат пациента, а Fix B-обновление профиля
    // таргетило уже новую запись вместо выбранной карточки.
    const normalBranch = extractSourceBlock(
      source,
      'В обычном режиме (не edit) создаем пациента если нужно',
      'Fix B: явное сохранение правок профиля выбранной карточки (обычный режим)'
    );
    // retained-карточка восстанавливается как цель сабмита
    const retainedBlock = extractSourceBlock(
      normalBranch,
      'Fix B (Codex R3 PR 3090, P1): карточка ЯВНО выбрана в этой сессии',
      'audit/phase-2, BS-52'
    );
    expect(retainedBlock).toContain('patientId = selectedPatientCardIdRef.current;');
    // и создание пациента выполняется ТОЛЬКО когда retained-карточки нет
    expect(normalBranch).toContain('if (!selectedPatientCardIdRef.current) {');
    expect(normalBranch).toContain('await createPatient(patientData)');
    // порядок: восстановление цели стоит РАНЬШЕ блока создания
    expect(normalBranch.indexOf('patientId = selectedPatientCardIdRef.current;')).toBeLessThan(
      normalBranch.indexOf('await createPatient(patientData)')
    );
  });

  it('own retained card is not reported as a foreign phone conflict (Codex R3 PR 3090)', () => {
    const checkBlock = extractSourceBlock(
      source,
      'Fix B (Codex R3 PR 3090): карточка, выбранная в этой сессии, не является',
      'setPhoneError({'
    );
    expect(checkBlock).toContain('existingPatient.id !== selectedPatientCardIdRef.current');
  });

  it('backend PatientUpdate schema accepts full_name with the create contract limit (Codex R3 PR 3090 P2 regression)', () => {
    const schema = fs.readFileSync(backendSchemaPath, 'utf8');
    const updateBlock = extractSourceBlock(schema, 'class PatientUpdate(ORMModel):', 'birth_date: date | None = None');
    // Лимит совпадает с PatientCreate (3 x 128 = 384): пациент, легитимно
    // созданный с ФИО 256-384 символа, обязан проходить и через PUT.
    expect(updateBlock).toContain('full_name: str | None = Field(None, max_length=384)');

    const service = fs.readFileSync(backendServicePath, 'utf8');
    expect(service).toContain('normalize_patient_name(full_name=str(raw_full_name).strip())');
    // schema-only поле не уходит в CRUD (у ORM full_name — hybrid property)
    expect(service).toContain('update_payload.pop("full_name", None)');
  });

  it('editing the FIO of a selected card keeps the visible identity (Codex R15 PR 3090 regression)', () => {
    // Регрессия R15: handlePatientSearch сбрасывал patient.id при ЛЮБОМ
    // вводе, поэтому PatientStepV2 помечал форму как «Новый», хотя скрытый
    // selectedPatientCardIdRef продолжал таргетить выбранную карточку —
    // сабмит обновлял того пациента, которого UI уже не показывал.
    // При выбранной карточке ID остаётся видимым: правка ФИО — это правка
    // выбранного пациента (Fix B R3), индикатор честный.
    const searchBlock = extractSourceBlock(
      source,
      'const handlePatientSearch = (value: string) => {',
      'setSearchTimeout(timeout);'
    );
    expect(searchBlock).toContain(
      'id: selectedPatientCardIdRef.current ? prev.patient.id : null'
    );
  });
});
