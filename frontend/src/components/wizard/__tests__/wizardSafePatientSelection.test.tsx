/**
 * Fix A (safe patient selection) — targeted regression tests.
 *
 * Два уровня проверки:
 *  1. Unit-тесты чистых хелперов wizardUtils (реальное поведение).
 *  2. Contract-тесты исходника визарда (структурные гарантии против
 *     регрессий авто-привязки и смешивания данных пациентов).
 *
 * Оригинальные дефекты:
 *  - произвольный HTTP 400 при создании пациента трактовался как
 *    «пациент уже существует» → авто-привязка к найденной по телефону карте;
 *  - правка ФИО после выбора карточки сбрасывала id, но оставляла адрес,
 *    телефон, дату рождения и разобранные части ФИО прежнего пациента;
 *  - editMode (QR): авто-привязка по телефону без подтверждения пользователя.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { beforeEach, describe, expect, it } from 'vitest';

import {
  PATIENT_SELECTED_FROM_CARD_FLAG,
  buildInheritedPatientClearPatch,
  isPatientSelectedFromCard,
  isPhoneDuplicateErrorMessage,
} from '../wizardUtils';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');

// =====================================================================
// 1. Pure helpers (real behavior)
// =====================================================================

describe('Fix A: isPhoneDuplicateErrorMessage', () => {
  it('recognizes the backend duplicate-phone 400 detail', () => {
    expect(
      isPhoneDuplicateErrorMessage('Пациент с таким номером телефона уже существует')
    ).toBe(true);
  });

  it('rejects unrelated 400 details (doc number duplicate, validation)', () => {
    expect(
      isPhoneDuplicateErrorMessage('Пациент с таким номером документа уже зарегистрирован')
    ).toBe(false);
    expect(isPhoneDuplicateErrorMessage('Некорректные данные пациента')).toBe(false);
    expect(isPhoneDuplicateErrorMessage('')).toBe(false);
    expect(isPhoneDuplicateErrorMessage(null)).toBe(false);
    expect(isPhoneDuplicateErrorMessage(undefined)).toBe(false);
  });
});

describe('Fix A: selected-card marker and inherited-field clear patch', () => {
  it('marks only explicitly selected cards', () => {
    expect(isPatientSelectedFromCard({ [PATIENT_SELECTED_FROM_CARD_FLAG]: true })).toBe(true);
    expect(isPatientSelectedFromCard({ fio: 'Иванов Иван' })).toBe(false);
    expect(isPatientSelectedFromCard(null)).toBe(false);
  });

  it('clear patch wipes every identity field that could mix two people', () => {
    const patch = buildInheritedPatientClearPatch() as Record<string, unknown>;
    expect(patch.birth_date).toBe('');
    expect(patch.phone).toBe('');
    expect(patch.address).toBe('');
    expect(patch.gender).toBe('');
    expect(patch.lastName).toBe('');
    expect(patch.firstName).toBe('');
    expect(patch.middleName).toBe('');
    expect(patch[PATIENT_SELECTED_FROM_CARD_FLAG]).toBe(false);
  });

  it('clear patch applied over a selected card leaves no inherited values', () => {
    const selectedCard = {
      id: 42,
      fio: 'Иванов Иван Иванович',
      birth_date: '1990-05-01',
      phone: '+998 90 123 45 67',
      address: 'ул. Навои, 1',
      gender: 'male',
      lastName: 'Иванов',
      firstName: 'Иван',
      middleName: 'Иванович',
      [PATIENT_SELECTED_FROM_CARD_FLAG]: true,
    };
    const patch = buildInheritedPatientClearPatch() as Record<string, unknown>;
    const cleared = { ...selectedCard, ...patch };
    // id намеренно НЕ входит в патч — вызывающая сторона сбрасывает его сама;
    // все прочие наследованные поля обязаны очиститься
    expect(cleared.birth_date).toBe('');
    expect(cleared.phone).toBe('');
    expect(cleared.address).toBe('');
    expect(cleared.gender).toBe('');
    expect(cleared.lastName).toBe('');
    expect(cleared.firstName).toBe('');
    expect(cleared.middleName).toBe('');
    expect(isPatientSelectedFromCard(cleared)).toBe(false);
  });
});

// =====================================================================
// 2. Wizard source contract (structural regression guards)
// =====================================================================

const extractSourceBlock = (source: string, startMarker: string, endMarker: string) => {
  const start = source.indexOf(startMarker);
  expect(start, `start marker not found: ${startMarker}`).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end, `end marker not found: ${endMarker}`).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('Fix A: wizard patient-selection contract', () => {
  let source = '';

  beforeEach(() => {
    source = readWizardSource();
  });

  it('does not auto-attach a phone-matched patient after patient-create 400', () => {
    const catchBlock = extractSourceBlock(
      source,
      'catch (createError: unknown) {',
      '// На этом этапе patientId должен быть определён'
    );

    // Авто-привязка удалена: присвоение patientId из найденной карты
    // в catch-блоке создания пациента запрещено.
    expect(catchBlock).not.toContain('patientId = foundPatient.id');
    // Дубликат телефона определяется по тексту ошибки, а не по любому 400.
    expect(catchBlock).toContain('isPhoneDuplicateErrorMessage(createErr.message)');
    // При конфликте — явная остановка с выбором пользователя.
    expect(catchBlock).toContain('\'misc.aw_patient_phone_conflict_stop\'');
    expect(catchBlock).toContain('setCurrentStep(STEP_PATIENT)');
  });

  it('clears inherited card fields when ФИО edit switches to a new patient', () => {
    const searchBlock = extractSourceBlock(
      source,
      'const handlePatientSearch = (value: string) => {',
      'const selectPatient = (patient: PatientRecord) => {'
    );

    expect(searchBlock).toContain('isPatientSelectedFromCard(wizardData.patient)');
    expect(searchBlock).toContain('buildInheritedPatientClearPatch()');
    expect(searchBlock).toContain('setFormattedBirthDate(\'\')');
    // editMode не затрагиваем: там правка ФИО = переименование той же карточки
    expect(searchBlock).toContain('!editMode && isPatientSelectedFromCard');
  });

  it('marks cards selected via selectPatient with the from-card flag', () => {
    const selectBlock = extractSourceBlock(
      source,
      'const selectPatient = (patient: PatientRecord) => {',
      'const handleBirthDateChange = (value: string) => {'
    );
    expect(selectBlock).toContain('_selectedFromCard: true');
  });

  it('requires explicit confirmation before edit-mode attach to a phone-matched card', () => {
    const editAttachBlock = extractSourceBlock(
      source,
      'if (editMode && !patientId && wizardData.patient.phone) {',
      'В обычном режиме (не edit) создаем пациента если нужно'
    );

    expect(editAttachBlock).toContain('identityMatches');
    expect(editAttachBlock).toContain('attachConfirmed');
    expect(editAttachBlock).toContain('\'misc.aw_attach_found_patient_title\'');
    // Отказ пользователя останавливает отправку и возвращает на шаг пациента
    expect(editAttachBlock).toContain('if (!attachConfirmed) {');
    expect(editAttachBlock).toContain('setCurrentStep(STEP_PATIENT)');
  });

  it('keeps explicit user choice UI for the live phone-duplicate check', () => {
    // Проверка уникальности телефона в реальном времени остаётся:
    // конфликт показывается сообщением + кнопкой явного выбора
    expect(source).toContain('aw_phone_already_exists');
  });
});
