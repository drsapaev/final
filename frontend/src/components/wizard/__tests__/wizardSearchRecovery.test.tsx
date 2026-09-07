/**
 * Fix F (search races & error recovery) — targeted tests.
 *
 * Оригинальные дефекты:
 *  - ответы поиска пациентов применялись в порядке прихода: устаревший
 *    ответ мог затереть результаты нового запроса;
 *  - после выбора карточки незавершённый debounce-поиск переоткрывал
 *    саджесты поверх выбранной карточки;
 *  - сетевой сбой поиска выглядел как «Пациенты не найдены — будет создан
 *    новый пациент» (подталкивало к дубликатам); состояния не различались;
 *  - закрытие мастера не отменяло незавершённые дебаунсы/поиски;
 *  - панельный Escape закрывал мастер в обход собственной защиты мастера;
 *  - закрытие с несохранёнными данными шло без предупреждения.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { beforeEach, describe, expect, it } from 'vitest';

import { wizardContentSignature } from '../wizardUtils';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const patientStepPath = path.resolve(__dirname, '../PatientStepV2.tsx');
const hotkeysPath = path.resolve(__dirname, '../../../pages/registrar/useRegistrarHotkeys.ts');
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');
const readPatientStepSource = () => fs.readFileSync(patientStepPath, 'utf8');
const readHotkeysSource = () => fs.readFileSync(hotkeysPath, 'utf8');

const extractSourceBlock = (source: string, startMarker: string, endMarker: string) => {
  const start = source.indexOf(startMarker);
  expect(start, `start marker not found: ${startMarker}`).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end, `end marker not found: ${endMarker}`).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('Fix F: wizard search-race contract', () => {
  let source = '';
  let patientStep = '';
  let hotkeys = '';

  beforeEach(() => {
    source = readWizardSource();
    patientStep = readPatientStepSource();
    hotkeys = readHotkeysSource();
  });

  it('only the latest patient-search response is applied', () => {
    const searchBlock = extractSourceBlock(
      source,
      'const searchPatients = useCallback(async (query: string) => {',
      'const handlePatientSearch = (value: string) => {'
    );
    expect(searchBlock).toContain('const requestId = ++patientSearchSeqRef.current;');
    expect(searchBlock).toContain('if (requestId !== patientSearchSeqRef.current)');
  });

  it('phone uniqueness check discards stale responses too', () => {
    const phoneBlock = extractSourceBlock(
      source,
      'const checkPhoneUniqueness = async (phone: string) => {',
      'const handlePhoneChange = (value: string) => {'
    );
    expect(phoneBlock).toContain('const requestId = ++phoneCheckSeqRef.current;');
  });

  it('selecting a card cancels the pending search (no suggestions re-open)', () => {
    const selectBlock = extractSourceBlock(
      source,
      'const selectPatient = (patient: PatientRecord) => {',
      'const handleBirthDateChange = (value: string) => {'
    );
    expect(selectBlock).toContain('patientSearchSeqRef.current += 1;');
    expect(selectBlock).toContain('setPatientSuggestions([]);');
  });

  it('search failure is an explicit error state, not «patients not found»', () => {
    const searchBlock = extractSourceBlock(
      source,
      'const searchPatients = useCallback(async (query: string) => {',
      'const handlePatientSearch = (value: string) => {'
    );
    expect(searchBlock).toContain("t('misc.aw_search_failed')");
    // empty-state скрывается при ошибке
    expect(patientStep).toContain('!searchError && suggestions.length === 0');
    expect(patientStep).toContain('onRetrySearch');
    expect(patientStep).toContain("t('misc.aw_search_retry')");
  });

  it('closing the wizard cancels pending debounces and search state', () => {
    const closeBlock = extractSourceBlock(
      source,
      '✅ ИСПРАВЛЕНО: Сброс состояния мастера при закрытии',
      'Safeguard: Ensure wizardData structure is valid'
    );
    expect(closeBlock).toContain('clearTimeout(searchTimeout)');
    expect(closeBlock).toContain('clearTimeout(phoneCheckTimeout)');
    expect(closeBlock).toContain('setPatientSearchError(null);');
  });

  it('close with user-entered content goes through a discard confirmation', () => {
    expect(source).toContain('const wizardHasUserContent = (): boolean => {');
    expect(source).toContain('const requestClose = async () => {');
    expect(source).toContain("t('misc.aw_discard_changes_title')");
    // Обе шапки мастера закрываются через защищённый requestClose
    expect(source).toContain('onClick={requestClose}');
  });

  it('close is blocked while processing (no fake cancellation)', () => {
    const requestCloseBlock = extractSourceBlock(
      source,
      'const requestClose = async () => {',
      'const requestCloseRef = useRef<() => void>(() => {});'
    );
    expect(requestCloseBlock).toContain('if (isProcessing) return;');
  });

  it('panel Escape no longer bypasses the wizard close guard', () => {
    expect(hotkeys).not.toContain('if (showWizard) setShowWizard(false);');
    // Мастер обрабатывает Escape сам — через requestClose
    const escBlock = extractSourceBlock(
      source,
      "if (e.key === 'Escape') {",
      '// Enter - следующий шаг (кроме textarea)'
    );
    expect(escBlock).toContain('requestCloseRef.current()');
  });

  it('no PHI draft storage introduced (in-memory only)', () => {
    expect(source).not.toContain('localStorage.setItem');
    expect(source).not.toContain('sessionStorage.setItem');
  });
});

// =====================================================================
// Codex R1 #3097 regressions
// =====================================================================

describe('Fix F Codex R1 regressions', () => {
  let source = '';

  beforeEach(() => {
    source = readWizardSource();
  });

  it('patient-search sequence is invalidated on input change, before debounce (P2)', () => {
    const handler = extractSourceBlock(
      source,
      'const handlePatientSearch = (value: string) => {',
      'const selectPatient = (patient: PatientRecord) => {'
    );
    // Инвалидация обязана происходить при каждом изменении ввода и ДО
    // планирования debounce-запроса
    const invalidateIdx = handler.indexOf('patientSearchSeqRef.current += 1;');
    const debounceIdx = handler.indexOf('setTimeout(() => searchPatients(value), 300)');
    expect(invalidateIdx).toBeGreaterThanOrEqual(0);
    expect(debounceIdx).toBeGreaterThan(invalidateIdx);
  });

  it('short-query invalidation clears the search spinner (P2)', () => {
    const earlyReturn = extractSourceBlock(
      source,
      'const searchPatients = useCallback(async (query: string) => {',
      '// Fix F: применяется только самый свежий ответ'
    );
    expect(earlyReturn).toContain('patientSearchSeqRef.current += 1;');
    expect(earlyReturn).toContain('setIsSearchingPatients(false);');
  });

  it('phone-lookup sequence is invalidated on every phone edit, including invalid values (P2)', () => {
    const handler = extractSourceBlock(
      source,
      'const handlePhoneChange = (value: string) => {',
      '// ===================== АВТОСОХРАНЕНИЕ ====================='
    );
    const invalidateIdx = handler.indexOf('phoneCheckSeqRef.current += 1;');
    const debounceIdx = handler.indexOf('setTimeout(() => checkPhoneUniqueness(formatted), 500)');
    expect(invalidateIdx).toBeGreaterThanOrEqual(0);
    expect(debounceIdx).toBeGreaterThan(invalidateIdx);
  });

  it('discard warning compares against the initial content snapshot, not p.id (P2)', () => {
    const hasContent = extractSourceBlock(
      source,
      'const wizardHasUserContent = (): boolean => {',
      'const requestCloseInFlightRef = useRef(false);'
    );
    // Новый контракт: diff с исходным снимком
    expect(hasContent).toContain('wizardContentSignature(');
    expect(hasContent).toContain('return current !== initialContentRef.current;');
    // Прежний контракт удалён: p.id сам по себе больше не «контент»
    expect(hasContent).not.toContain('p.id\n    );');
  });

  it('wizardContentSignature: unchanged edit data is stable, real edits change the signature (real behavior)', () => {
    // Codex R1 #3097: открыли существующую запись и сразу закрыли —
    // предупреждение о потере данных появляться не должно. Поведение
    // проверяется на реальной функции, а не на тексте исходника.
    const initialPatient = {
      id: 42,
      fio: 'SYNTHETIC-Тестов Тест',
      phone: '+998 00 000 00 02',
      address: 'ул. Тестовая, 1',
      birth_date: '1990-01-01',
      gender: 'male',
    };
    const initialCart = {
      items: [{ service_id: 7, doctor_id: null, quantity: 1 }],
      discount_mode: 'none',
      all_free: false,
    };

    const initialSignature = wizardContentSignature({ patient: initialPatient, cart: initialCart });

    // Те же данные, собранные заново (как это делает wizardHasUserContent) —
    // подпись обязана совпасть поразрядно
    expect(wizardContentSignature({ patient: { ...initialPatient }, cart: {
      items: initialCart.items.map((i) => ({ ...i })),
      discount_mode: 'none',
      all_free: false,
    } })).toBe(initialSignature);

    // Реальная правка любого поля меняет подпись
    expect(
      wizardContentSignature({
        patient: { ...initialPatient, fio: 'SYNTHETIC-Тестов Тестович' },
        cart: initialCart,
      })
    ).not.toBe(initialSignature);
    expect(
      wizardContentSignature({
        patient: initialPatient,
        cart: { ...initialCart, items: [{ service_id: 8, doctor_id: null, quantity: 1 }] },
      })
    ).not.toBe(initialSignature);

    // Форматирование телефона (пробелы) не считается изменением
    expect(
      wizardContentSignature({
        patient: { ...initialPatient, phone: '+998 00 000 00 02' },
        cart: initialCart,
      })
    ).toBe(initialSignature);
  });
});
