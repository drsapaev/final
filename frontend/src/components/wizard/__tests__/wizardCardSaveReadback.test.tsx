/**
 * E-054 leftover 2 (wizard-пятёрка PR 3086, закрыт как superseded) —
 * read-back верификация сохранения карточки пациента.
 *
 * Дефект на main: ошибка PUT карточки на обычном пути проглатывалась
 * (catch → logger.warn → продолжение) и корзина создавалась с
 * несохранёнными правками карточки (тихая потеря данных); 200 OK не
 * проверялся фактическим перечитыванием.
 *
 * Фикс: после PUT — getPatient + сверка каждого отправленного поля
 * (findCardPersistMismatches); расхождение или ошибка → остановка
 * отправки без корзины (toast, wizard остаётся открытым).
 *
 * RED→GREEN: на main до фикса source-контракты падали (в блоке needsUpdate
 * не было getPatient/findCardPersistMismatches/тостов), unit-тесты не
 * импортировались (функций не существовало).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  findCardPersistMismatches,
  normalizeCardPersistValue,
} from '../wizardUtils';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');

const extractSourceBlock = (source: string, startMarker: string, endMarker: string) => {
  const start = source.indexOf(startMarker);
  expect(start, `start marker not found: ${startMarker}`).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end, `end marker not found: ${endMarker}`).toBeGreaterThan(start);
  return source.slice(start, end);
};

// ---------------------------------------------------------------------------
// Чистые функции сравнения (unit)
// ---------------------------------------------------------------------------

describe('normalizeCardPersistValue', () => {
  it('birth_date: ДД.ММ.ГГГГ сводится к ISO (формат-толерантное сравнение)', () => {
    expect(normalizeCardPersistValue('birth_date', '28.02.2002')).toBe('2002-02-28');
  });

  it('birth_date: ISO проходит как есть', () => {
    expect(normalizeCardPersistValue('birth_date', '2002-02-28')).toBe('2002-02-28');
  });

  it('sex: регистр не влияет', () => {
    expect(normalizeCardPersistValue('sex', 'm')).toBe(normalizeCardPersistValue('sex', 'M'));
  });

  it('строковые поля тримятся', () => {
    expect(normalizeCardPersistValue('address', '  ул. Абая 1  ')).toBe('ул. Абая 1');
  });

  it('null/undefined → пустая строка', () => {
    expect(normalizeCardPersistValue('address', null)).toBe('');
    expect(normalizeCardPersistValue('sex', undefined)).toBe('');
  });
});

describe('findCardPersistMismatches', () => {
  it('полное совпадение → пустой список', () => {
    const sent = { birth_date: '28.02.2002', sex: 'M', address: 'ул. Абая 1' };
    const readBack = { birth_date: '2002-02-28', sex: 'M', address: 'ул. Абая 1' };
    expect(findCardPersistMismatches(sent, readBack)).toEqual([]);
  });

  it('несохранённое поле попадает в отчёт с обоими значениями', () => {
    const sent = { address: 'новый адрес' };
    const readBack = { address: 'старый адрес' };
    expect(findCardPersistMismatches(sent, readBack)).toEqual([
      { field: 'address', sent: 'новый адрес', readBack: 'старый адрес' },
    ]);
  });

  it('readBack отсутствует → все отправленные поля несохранены', () => {
    const sent = { sex: 'F', address: 'x' };
    const result = findCardPersistMismatches(sent, null);
    expect(result.map((m) => m.field)).toEqual(['sex', 'address']);
    expect(result[0].readBack).toBeUndefined();
  });

  it('ничего не отправлено → нечего сверять', () => {
    expect(findCardPersistMismatches({}, { sex: 'M' })).toEqual([]);
  });

  it('сравнивает только ОТПРАВЛЕННЫЕ поля (лишние в карточке игнорируются)', () => {
    const sent = { sex: 'M' };
    const readBack = { sex: 'M', address: 'чужое поле, которое не отправлялось' };
    expect(findCardPersistMismatches(sent, readBack)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Source-контракты мастера (блок needsUpdate обычного пути)
// ---------------------------------------------------------------------------

describe('wizard card-save readback contract', () => {
  let source = '';

  beforeEach(() => {
    source = readWizardSource();
  });

  const cardSaveBlock = () =>
    extractSourceBlock(
      source,
      'const updateData: Record<string, unknown> = {};',
      '✅ НОВОЕ: Если в режиме редактирования по QR пациент по телефону не найден',
    );

  it('после PUT карточка перечитывается (getPatient read-back)', () => {
    expect(cardSaveBlock()).toContain('getPatient(');
    expect(cardSaveBlock()).toContain('findCardPersistMismatches(');
  });

  it('ошибка сохранения останавливает отправку (тост + return, не logger.warn-проглатывание)', () => {
    expect(cardSaveBlock()).toContain('t(\'misc.aw_patient_profile_save_failed\'');
    expect(cardSaveBlock()).toContain('t(\'misc.aw_patient_profile_verify_failed\')');
    // старое проглатывание отсутствует: в catch после logger.error стоит return
    const catchBlock = cardSaveBlock().slice(cardSaveBlock().indexOf('} catch (e: unknown)'));
    expect(catchBlock).toContain('return;');
    expect(catchBlock).not.toContain('logger.warn(\'⚠️ Failed to update patient:\'');
  });

  it('сиротские i18n-ключи верификации подключены (были только в локалях)', () => {
    expect(source).toContain('t(\'misc.aw_patient_profile_save_failed\'');
    expect(source).toContain('t(\'misc.aw_patient_profile_verify_failed\'');
  });
});
