/**
 * Fix E (keyboard & validation) — targeted tests.
 *
 * Оригинальные дефекты:
 *  - 31.02.2020 проходил validateStep(1): проверялись только диапазоны
 *    1..31 / 1..12 / год 1900..текущий; будущие даты в текущем году тоже
 *    проходили (например, декабрь текущего года);
 *  - оба gender-radio были tabIndex=-1, когда пол не выбран — группа
 *    недостижима с клавиатуры;
 *  - глобальный обработчик Enter делал preventDefault на всём: Enter на
 *    кнопках (саджесты пациентов, услуги, кнопки вложенных диалогов)
 *    не «нажимал» кнопку, а прыгал к следующему шагу.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { beforeEach, describe, expect, it } from 'vitest';

import { getBirthDateValidationError } from '../wizardUtils';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const patientStepPath = path.resolve(__dirname, '../PatientStepV2.tsx');
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');
const readPatientStepSource = () => fs.readFileSync(patientStepPath, 'utf8');

const extractSourceBlock = (source: string, startMarker: string, endMarker: string) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

// =====================================================================
// 1. Birth date calendar validation (real behavior)
// =====================================================================

describe('Fix E: getBirthDateValidationError', () => {
  it('accepts a valid full date and an empty value (optional field)', () => {
    expect(getBirthDateValidationError('15.08.1990')).toBe('ok');
    expect(getBirthDateValidationError('29.02.2024')).toBe('ok'); // високосный
    expect(getBirthDateValidationError('')).toBe('empty');
    expect(getBirthDateValidationError('00.00.0000')).toBe('empty');
  });

  it('rejects non-existent calendar dates (31.02, 30.02, 31.04)', () => {
    expect(getBirthDateValidationError('31.02.2020')).toBe('invalid');
    expect(getBirthDateValidationError('30.02.2021')).toBe('invalid');
    expect(getBirthDateValidationError('31.04.1995')).toBe('invalid');
    expect(getBirthDateValidationError('29.02.2023')).toBe('invalid'); // не високосный
  });

  it('rejects future dates — not just future years', () => {
    const future = new Date();
    future.setMonth(future.getMonth() + 2); // заведомо в будущем в текущем году
    const dd = String(future.getDate()).padStart(2, '0');
    const mm = String(future.getMonth() + 1).padStart(2, '0');
    const yyyy = String(future.getFullYear());
    expect(getBirthDateValidationError(`${dd}.${mm}.${yyyy}`)).toBe('future');
    // Вчерашняя дата валидна
    const past = new Date(future.getFullYear() - 30, future.getMonth(), future.getDate() - 1);
    const pdd = String(past.getDate()).padStart(2, '0');
    const pmm = String(past.getMonth() + 1).padStart(2, '0');
    expect(
      getBirthDateValidationError(`${pdd}.${pmm}.${past.getFullYear()}`)
    ).toBe('ok');
  });

  it('treats partial input as incomplete (never silently empty)', () => {
    expect(getBirthDateValidationError('31.02')).toBe('incomplete');
    expect(getBirthDateValidationError('3102')).toBe('incomplete');
    expect(getBirthDateValidationError('15.08.19')).toBe('incomplete');
    expect(getBirthDateValidationError('15.08.19900')).toBe('incomplete');
  });
});

// =====================================================================
// 2. Source contracts
// =====================================================================

describe('Fix E: keyboard & validation contract', () => {
  let source = '';
  let patientStep = '';

  beforeEach(() => {
    source = readWizardSource();
    patientStep = readPatientStepSource();
  });

  it('validateStep uses the calendar validator and reports future dates distinctly', () => {
    expect(source).toContain('getBirthDateValidationError(formattedBirthDate)');
    expect(source).toContain("t('misc.aw_birth_date_future')");
    // Прежний неполный валидатор удалён
    expect(source).not.toContain('yearNum > new Date().getFullYear()');
  });

  it('Enter is not hijacked from interactive controls (buttons, links, selects)', () => {
    expect(source).toContain("const interactiveTags = ['BUTTON', 'A', 'SELECT'];");
    expect(source).toContain('if (isInteractiveTarget) return;');
  });

  it('Ctrl+Enter completion is handled BEFORE the interactive-target guard (Codex R1)', () => {
    // Регрессия R1: guard `if (isInteractiveTarget) return;` стоял раньше
    // блока Ctrl+Enter, поэтому фокус на BUTTON/A/SELECT/contenteditable
    // гасил задокументированный глобальный шорткат «Завершить».
    const hotkeys = extractSourceBlock(
      source,
      '===================== ГОРЯЧИЕ КЛАВИШИ =====================',
      'document.addEventListener(\'keydown\', handleKeyDown);'
    );
    const ctrlEnterIdx = hotkeys.indexOf("if (e.key === 'Enter' && e.ctrlKey)");
    const guardIdx = hotkeys.indexOf('if (isInteractiveTarget) return;');
    expect(ctrlEnterIdx).toBeGreaterThanOrEqual(0);
    expect(guardIdx).toBeGreaterThan(ctrlEnterIdx);
    // Ctrl+Enter-ветка завершает обработку: следующая не «проваливается» в guard
    expect(hotkeys.slice(ctrlEnterIdx, guardIdx)).toContain('return;');
  });

  it('gender radio group is reachable by keyboard when nothing is selected', () => {
    expect(patientStep).toContain(
      'selectedGender === gender || (!selectedGender && gender === \'male\') ? 0 : -1'
    );
  });

  it('arrow keys move DOM focus together with the selection (Codex R2)', () => {
    // Регрессия R2: обработчик стрелок вычислял следующий вариант из
    // selectedGender и НЕ перемещал DOM-фокус. При пустом selectedGender
    // ArrowRight выбирал male повторно, а последующие стрелки меняли
    // значение, оставляя фокус на кнопке с tabIndex=-1.
    const radioBlock = extractSourceBlock(
      patientStep,
      'role="radiogroup"',
      'errors.gender &&'
    );
    // Следующий вариант — из фокусного элемента/направления, а не только из значения
    expect(radioBlock).toContain("document.activeElement");
    expect(radioBlock).toContain("e.key === 'ArrowRight' ? 1 : -1");
    // Фокус следует за выбором (roving tabindex)
    expect(radioBlock).toContain('genderRadioRefs.current[nextIdx]?.focus()');
    // Кнопки регистрируют DOM-ссылки и помечены data-gender
    expect(patientStep).toContain('ref={(el) => { genderRadioRefs.current[genderIdx] = el; }}');
    expect(patientStep).toContain('data-gender={gender}');
  });
});
