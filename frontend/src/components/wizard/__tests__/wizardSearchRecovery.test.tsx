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

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useEffect, useState } from 'react';

import {
  parseWizardBaseline,
  patchBaselineWithResolvedServiceIds,
  refreshBaselineAfterGenderHydration,
  refreshBaselineAfterServiceResolution,
  useWizardSearchUnmountCleanup,
  wizardContentSignature,
} from '../wizardUtils';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const patientStepPath = path.resolve(__dirname, '../PatientStepV2.tsx');
const hotkeysPath = path.resolve(__dirname, '../../../pages/registrar/useRegistrarHotkeys.ts');
const confirmDialogPath = path.resolve(__dirname, '../../common/ConfirmDialog.tsx');
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');
const readPatientStepSource = () => fs.readFileSync(patientStepPath, 'utf8');
const readHotkeysSource = () => fs.readFileSync(hotkeysPath, 'utf8');
const readWizardUtilsSource = () => fs.readFileSync(path.resolve(__dirname, '../wizardUtils.ts'), 'utf8');

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

  it('clearing the form invalidates the in-flight search and phone check', () => {
    // Codex R10 PR 3097 (P2): «Очистить форму» при незавершённом поиске
    // раньше НЕ инвалидирует запрос — его catch восстанавливал баннер
    // ошибки на пустой форме (с Retry, которому нечего перезапускать).
    // Теперь и clearDraft, и закрытие вызывают общий resetSearchInteractionState.
    const clearBlock = extractSourceBlock(
      source,
      'const clearDraft = () => {',
      'toast.success(t(\'misc.aw_form_cleared\'));'
    );
    expect(clearBlock).toContain('resetSearchInteractionState();');

    const helperBlock = extractSourceBlock(
      source,
      'const resetSearchInteractionState = () => {',
      '};\n\n  // Safeguard'
    );
    // seq +1 делает ответ in-flight запроса устаревшим (catch не применит его)
    expect(helperBlock).toContain('patientSearchSeqRef.current += 1;');
    expect(helperBlock).toContain('phoneCheckSeqRef.current += 1;');
    // отложенные debounce-таймеры снимаются — отложенный поиск не стартует
    // уже после очистки/закрытия
    expect(helperBlock).toContain('clearTimeout(t)');
    // спиннер и саджесты гасятся, ошибка поиска снимается — состояние чистое
    expect(helperBlock).toContain('setIsSearchingPatients(false);');
    expect(helperBlock).toContain('setPatientSuggestions([]);');
    expect(helperBlock).toContain('setShowSuggestions(false);');
    expect(helperBlock).toContain('setPatientSearchError(null);');
  });

  it('closing the wizard cancels pending debounces and search state', () => {
    const closeBlock = extractSourceBlock(
      source,
      '✅ ИСПРАВЛЕНО: Сброс состояния мастера при закрытии',
      'Safeguard: Ensure wizardData structure is valid'
    );
    // Codex R10 PR 3097: сброс вынесен в общий resetSearchInteractionState —
    // закрытие проходит через него (те же гарантии Fix F).
    expect(closeBlock).toContain('resetSearchInteractionState();');
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
// Codex R1 PR 3097 regressions
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

  it('auto-hydration (service_id / gender) refreshes the dirty baseline (Codex R2 P2)', () => {
    // Codex R2 PR 3097: резолвинг вынесен в чистую функцию (потолок LOC PR-45),
    // эффект гидрации обязан перезаписывать снимок после разрешённого service_id.
    const hydration = extractSourceBlock(
      source,
      'const resolution = resolveCartServiceReferences(',
      '}, [servicesData, wizardData.cart.items]);'
    );
    // Codex R3 PR 3097: подпись снимка обновляется через refresh-хелпер
    // (только гидрированный service_id, без переснимка живого состояния)
    expect(hydration).toContain('if (refreshedBaseline) initialContentRef.current = refreshedBaseline;');

    // Сама чистая функция резолвит service_id по коду (p09 = p9) и имени
    const utilsSource = readWizardUtilsSource();
    const resolver = extractSourceBlock(
      utilsSource,
      'export const resolveCartServiceReferences = (',
      'return changed ? { items: updatedItems, changed } : null;'
    );
    expect(resolver).toContain('service_id: foundService.id');
    expect(resolver).toContain("replace(/^([A-Z])0+(\\d+)$/, '$1$2')");

    const genderBlock = extractSourceBlock(
      source,
      'const hydrateMissingEditGender = async () => {',
      'hydrateMissingEditGender();'
    );
    expect(genderBlock).toContain('if (genderBaseline) initialContentRef.current = genderBaseline;');
  });

  it('baseline refresh patches ONLY auto-hydrated fields, never live user edits (Codex R3 #3097 P2 regression)', () => {
    // Прежний баг: переснимок живого wizardData копировал в снимок правки
    // пользователя (ФИО/телефон/врач/количество), сделанные, пока шёл запрос
    // /registrar/services, — и закрытие молча теряло их.
    const hydration = extractSourceBlock(
      source,
      'const resolution = resolveCartServiceReferences(',
      '}, [servicesData, wizardData.cart.items]);'
    );
    // снимок патчится из ИСХОДНОГО снимка, а не из живого состояния
    expect(hydration).toContain('refreshBaselineAfterServiceResolution(initialContentRef.current');
    expect(hydration).not.toContain('fio: wizardData.patient.fio');
    expect(hydration).not.toContain('phone: wizardData.patient.phone');

    const genderBlock = extractSourceBlock(
      source,
      'const hydrateMissingEditGender = async () => {',
      'hydrateMissingEditGender();'
    );
    expect(genderBlock).toContain('refreshBaselineAfterGenderHydration(initialContentRef.current');
    expect(genderBlock).not.toContain('fio: wizardData.patient.fio');

    // чистые хелперы: патч только service_id, снятие при расхождении длины
    const utilsSource = readWizardUtilsSource();
    const patcher = extractSourceBlock(
      utilsSource,
      'export const patchBaselineWithResolvedServiceIds = (',
      'return baselineItems.map((item, index) => {'
    );
    expect(patcher).toContain('baselineItems.length !== resolvedItems.length');
  });

  it('wizard shortcuts are suppressed while the confirm dialog is open (Codex R3 #3097 P2 regression)', () => {
    // Прежний баг: Enter на кнопках модального диалога подтверждения
    // preventDefault'ился и продвигал/отправлял мастер под диалогом; на
    // последнем шаге второй confirm() заменял ожидающий диалог.
    const handler = extractSourceBlock(
      source,
      'const handleKeyDown = (e: KeyboardEvent) => {',
      "document.addEventListener('keydown', handleKeyDown);"
    );
    expect(handler).toContain('if (confirmDialogOpenRef.current) return;');
    // Codex R9 PR 3097 (P1): флаг открытости выводится ЛОКАЛЬНО в мастере
    // (обёртка confirm-функции); общий useConfirm остаётся в исходном
    // 2-элементном контракте — shared-файлы вне скоупа PR не меняются.
    expect(source).toContain('confirmDialogOpenRef.current = true;');
    expect(source).toContain('confirmDialogOpenRef.current = false;');
    const dialogSource = fs.readFileSync(confirmDialogPath, 'utf8');
    expect(dialogSource).toContain('return [confirm, dialog] as [');
    expect(dialogSource).not.toContain('state.isOpen] as [');
  });

  it('Enter on the retry button activates the button, not the wizard shortcut (Codex R2 P2)', () => {
    const retryBlock = extractSourceBlock(
      readPatientStepSource(),
      'onClick={onRetrySearch}',
      "{t('misc.aw_search_retry')}"
    );
    expect(retryBlock).toContain("if (e.key === 'Enter' || e.key === ' ')");
    expect(retryBlock).toContain('e.stopPropagation()');
  });

  it('wizardContentSignature: unchanged edit data is stable, real edits change the signature (real behavior)', () => {
    // Codex R1 PR 3097: открыли существующую запись и сразу закрыли —
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

describe('Fix F (Codex R3 #3097): baseline patch helpers', () => {
  const baseline = wizardContentSignature({
    patient: { id: 7, fio: 'SYNTHETIC-Тестов Тест', phone: '+998000000001', address: '', birth_date: '1990-01-01', gender: '' },
    cart: { items: [{ service_id: null, doctor_id: 3, quantity: 1 }, { service_id: 9, doctor_id: null, quantity: 2 }], discount_mode: 'none', all_free: false },
  });

  it('parseWizardBaseline round-trips the signature and rejects malformed input', () => {
    const parsed = parseWizardBaseline(baseline);
    expect(parsed).not.toBeNull();
    expect(parsed?.patient.fio).toBe('SYNTHETIC-Тестов Тест');
    expect(parsed?.cart.items).toHaveLength(2);

    expect(parseWizardBaseline('')).toBeNull();
    expect(parseWizardBaseline('not json {')).toBeNull();
    expect(parseWizardBaseline('{"patient": {}}')).toBeNull();
  });

  it('patch fills ONLY missing service_ids and keeps user-editable baseline fields', () => {
    const parsed = parseWizardBaseline(baseline);
    const resolved = [
      { service_id: 12, service_name: 'X', service_price: 100, doctor_id: 3, quantity: 1 },
      { service_id: 9, service_name: 'Y', service_price: 200, doctor_id: null, quantity: 2 },
    ];
    const patched = patchBaselineWithResolvedServiceIds(parsed!.cart.items, resolved as unknown as Array<Record<string, unknown>>);

    expect((patched[0] as { service_id: number }).service_id).toBe(12);
    // уже идентифицированная позиция не меняется
    expect((patched[1] as { service_id: number }).service_id).toBe(9);
    // quantity/doctor_id снимка не перезаписываются живым состоянием
    expect((patched[0] as { quantity: number }).quantity).toBe(1);
    expect((patched[1] as { doctor_id: number | null }).doctor_id).toBeNull();

    // подпись со снятым снимком отличается ТОЛЬКО гидрацией service_id
    const reSigned = wizardContentSignature({ patient: parsed!.patient, cart: { ...parsed!.cart, items: patched } });
    expect(reSigned).not.toBe(baseline);
    expect(JSON.parse(reSigned).cart.items[0].service_id).toBe(12);
    expect(JSON.parse(reSigned).patient.fio).toBe('SYNTHETIC-Тестов Тест');
  });

  it('length mismatch (user added/removed items mid-flight) leaves the baseline untouched', () => {
    const parsed = parseWizardBaseline(baseline);
    const shorter = [{ service_id: 12 }];
    const patched = patchBaselineWithResolvedServiceIds(parsed!.cart.items, shorter as unknown as Array<Record<string, unknown>>);
    expect(patched).toBe(parsed!.cart.items); // тот же массив — снимок не тронут
  });
});

describe('Fix F (Codex R3 #3097): refresh helpers keep user edits out of the baseline', () => {
  const base = wizardContentSignature({
    patient: { id: 7, fio: 'SYNTHETIC-Тестов Тест', phone: '+998000000001', address: 'ул. А', birth_date: '1990-01-01', gender: '' },
    cart: { items: [{ service_id: null, doctor_id: 3, quantity: 1 }], discount_mode: 'none', all_free: false },
  });
  const resolved = [{ service_id: 12, service_name: 'X', service_price: 100, doctor_id: 3, quantity: 1 }] as unknown as Array<Record<string, unknown>>;

  it('service resolution refresh: only service_id changes, user fields untouched', () => {
    const refreshed = refreshBaselineAfterServiceResolution(base, resolved);
    expect(refreshed).not.toBeNull();
    const obj = JSON.parse(refreshed as string);
    expect(obj.cart.items[0].service_id).toBe(12);
    // правки пользователя НЕ попали в снимок: fio/address остаются исходными
    expect(obj.patient.fio).toBe('SYNTHETIC-Тестов Тест');
    expect(obj.patient.address).toBe('ул. А');
  });

  it('gender hydration refresh: only gender changes, service hydration preserved', () => {
    const afterService = refreshBaselineAfterServiceResolution(base, resolved) as string;
    const afterGender = refreshBaselineAfterGenderHydration(afterService, 'male') as string;
    const obj = JSON.parse(afterGender);
    expect(obj.patient.gender).toBe('male');
    expect(obj.patient.fio).toBe('SYNTHETIC-Тестов Тест');
    expect(obj.cart.items[0].service_id).toBe(12);

    // повреждённый снимок → null (снимок остаётся как был)
    expect(refreshBaselineAfterGenderHydration('broken {', 'male')).toBeNull();
    expect(refreshBaselineAfterServiceResolution('broken {', resolved)).toBeNull();
  });
});

describe('Fix F (Codex R4 #3097): partial birth-date input tracked in dirty state', () => {
  it('wizardHasUserContent falls back to the visible mask value when ISO is empty (P2 regression)', () => {
    // Прежний баг: частичный ввод даты («01.0») жил только в formattedBirthDate,
    // ISO оставался пустым и совпадал с пустым baseline — закрытие молча теряло
    // видимый ввод.
    const source = fs.readFileSync(wizardPath, 'utf8');
    const hasContent = source.slice(
      source.indexOf('const wizardHasUserContent = (): boolean => {'),
      source.indexOf('return current !== initialContentRef.current;')
    );
    expect(hasContent).toContain(
      "birth_date: p.birth_date || convertDateToISO(formattedBirthDate) || formattedBirthDate || ''"
    );
  });
});

describe('Fix F (Codex R7 #3097): unmount-only debounce cleanup', () => {
  // Поведенческий стенд: таймер хранится в state, как в мастере
  // (setSearchTimeout/setPhoneCheckTimeout), хук — единственный,
  // кто гасит его вне обработчиков.
  const useDebounceHarness = (fire: () => void) => {
    const [timer, setTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
    useWizardSearchUnmountCleanup(() => [timer]);
    useEffect(() => {
      const t = setTimeout(fire, 300);
      setTimer(t);
    }, []);
    return timer;
  };

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('pending debounce survives an unrelated re-render inside the window (R7 P2)', () => {
    const onFire = vi.fn();
    const { rerender } = renderHook(({ fire }: { fire: () => void }) => useDebounceHarness(fire), {
      initialProps: { fire: onFire },
    });
    // Посторонний ререндер в окне дебаунса (услуги/врачи догрузились):
    // прежний cleanup-на-каждом-рендере гасил валидный таймер — поиск/проверка
    // телефона молча не выполнялись.
    rerender({ fire: onFire });
    act(() => {
      vi.advanceTimersByTime(350);
    });
    expect(onFire).toHaveBeenCalledTimes(1);
  });

  it('real unmount still cancels the pending debounce (R5 invariant)', () => {
    const onFire = vi.fn();
    const { unmount } = renderHook(({ fire }: { fire: () => void }) => useDebounceHarness(fire), {
      initialProps: { fire: onFire },
    });
    act(() => {
      unmount();
    });
    act(() => {
      vi.advanceTimersByTime(350);
    });
    expect(onFire).not.toHaveBeenCalled();
  });
});
