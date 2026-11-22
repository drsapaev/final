/**
 * REG-FE-081 / REG-FE-082 + CSH-FE-043/044/045 (follow-up audit
 * 2026-11-02): честность печатного конвейера panelPrint.
 *
 * 081: явно назначенный приём (visit_date + visit_time) обязан стоять ВЫШЕ
 *      штампа регистрации в очереди (queue_time). Прежде getFirstDefined(
 *      appointment_time, queue_time, ...) возвращал queue_time ДО проверки
 *      visit_date/visit_time — пациент с приёмом 03.11 14:00, зарегистрированный
 *      в очереди 02.11 09:00, получал на талоне штамп регистрации.
 *      Регистрационный источник помечается отдельной меткой «Время регистрации».
 * 082: при недоступных настройках клиники талон печатается БЕЗ бренда —
 *      прежде дефолт молча подставлял «Programma Clinic» (чужая идентичность
 *      для любого другого развёртывания). Снапшот строки (row.clinic_name)
 *      по-прежнему работает.
 * 043: «синхронная» обёртка printPanelTicketInBrowser (возвращала true
 *      безусловно) удалена из модуля.
 * 044: успех талона включает честный вызов print(): исключение print()
 *      больше не маскируется; квитанция возвращает типизированный исход.
 * 045: пакетная печать одним документом: окно открывается синхронно
 *      (openPanelTicketBatchWindow) с плейсхолдером, затем наполняется
 *      единым HTML со всеми талонами.
 *
 * Red-first (до фикса): все сценарии ниже проваливались (payload нес
 *      штамп регистрации вместо visit_date+visit_time; html содержал
 *      'Programma Clinic' при сбое настроек; обёртка существовала и т.д.).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/adminSettings', () => ({
  fetchClinicSettings: vi.fn(),
}));

vi.mock('../../api/ticketPrintSettings', async () => {
  const actual = await vi.importActual<typeof import('../../api/ticketPrintSettings')>('../../api/ticketPrintSettings');
  return {
    ...actual,
    fetchTicketPrintSettings: vi.fn(),
  };
});

import { fetchClinicSettings } from '../../api/adminSettings';
import { TICKET_PRINT_SETTINGS_DEFAULTS, fetchTicketPrintSettings } from '../../api/ticketPrintSettings';
import * as panelPrintModule from '../panelPrint';
import {
  buildPanelTicketPayload,
  buildPanelTicketPrintableHtml,
  buildPanelTicketsBatchPrintableHtml,
  openPanelTicketBatchWindow,
  printPanelReceiptInBrowser,
  printPanelTicketInBrowserAsync,
  printPanelTicketsBatchInExistingWindow,
} from '../panelPrint';

const fetchTicketPrintSettingsMock = fetchTicketPrintSettings as unknown as ReturnType<typeof vi.fn>;
const fetchClinicSettingsMock = fetchClinicSettings as unknown as ReturnType<typeof vi.fn>;

const FULFILLED_SETTINGS = [{ key: 'clinic_name', value: 'City Clinic' }, { key: 'logo_url', value: '/static/city-logo.png' }];

const originalOpen = window.open;

type FakeWindowOptions = { readyState?: string; printImpl?: () => void };

const makeFakeWindow = ({ readyState = 'complete', printImpl }: FakeWindowOptions = {}) =>
  ({
    closed: false,
    document: {
      open: vi.fn(),
      write: vi.fn(),
      close: vi.fn(),
      readyState,
    },
    focus: vi.fn(),
    print: vi.fn(printImpl ?? (() => {})),
    close: vi.fn(),
  }) as unknown as Window & typeof globalThis;

beforeEach(() => {
  fetchTicketPrintSettingsMock.mockReset();
  fetchClinicSettingsMock.mockReset();
  fetchTicketPrintSettingsMock.mockResolvedValue({ ...TICKET_PRINT_SETTINGS_DEFAULTS });
  fetchClinicSettingsMock.mockResolvedValue(FULFILLED_SETTINGS);
});

afterEach(() => {
  window.open = originalOpen;
  vi.restoreAllMocks();
});

describe('REG-FE-081 — scheduled visit outranks queue registration stamp', () => {
  it('payload: queue_time present + explicit visit_date/visit_time → scheduled wins', () => {
    const row = {
      queue_number: 17,
      queue_time: '2026-11-02T09:00:00+05:00',
      visit_date: '2026-11-03',
      visit_time: '14:00',
    };
    const payload = buildPanelTicketPayload(row);
    // Прежде: time_window брался из queue_time (штамп регистрации), а
    // visit_date/visit_time игнорировались, если queue_time парсится.
    expect(payload.time_window).toBe('03.11.2026 14:00');
    expect(payload.time_window_source).toBe('scheduled');
  });

  it('payload: canonical appointment_time still wins over visit_date/visit_time', () => {
    const row = {
      queue_number: 18,
      appointment_time: '2026-11-05T10:30:00+05:00',
      visit_date: '2026-11-06',
      visit_time: '12:00',
      queue_time: '2026-11-05T10:00:00+05:00',
    };
    const payload = buildPanelTicketPayload(row);
    expect(payload.time_window_source).toBe('appointment');
  });

  it('payload: registration-only row → source registration (labelled, not masquerading as a visit time)', () => {
    const row = {
      queue_number: 19,
      queue_time: '2026-11-02T09:00:00+05:00',
    };
    const payload = buildPanelTicketPayload(row);
    expect(payload.time_window_source).toBe('registration');
    expect(payload.time_window).toBeTruthy();
  });

  it('rendered html: registration-only ticket is labelled «Время регистрации», scheduled — «Дата и время»', async () => {
    const registrationHtml = await buildPanelTicketPrintableHtml({
      queue_number: 19,
      queue_time: '2026-11-02T09:00:00+05:00',
    });
    expect(registrationHtml).toContain('Время регистрации:');
    expect(registrationHtml).not.toContain('Дата и время:');

    const scheduledHtml = await buildPanelTicketPrintableHtml({
      queue_number: 20,
      queue_time: '2026-11-02T09:00:00+05:00',
      visit_date: '2026-11-03',
      visit_time: '14:00',
    });
    expect(scheduledHtml).toContain('03.11.2026 14:00');
    expect(scheduledHtml).toContain('Дата и время:');
    expect(scheduledHtml).not.toContain('Время регистрации:');
  });
});

describe('REG-FE-082 — no foreign clinic brand substitution', () => {
  it('settings failure + row without clinic_name → UNBRANDED ticket (no Programma Clinic)', async () => {
    fetchClinicSettingsMock.mockRejectedValue(new Error('settings 500'));
    const html = await buildPanelTicketPrintableHtml({ queue_number: 21 });
    expect(html).not.toContain('Programma Clinic');
    // Рендер бренда отсутствует (в <style> класс определён, но не инстанцирован).
    expect(html).not.toContain('class="clinic-name"');
    expect(html).not.toContain('class="clinic-brand"');
  });

  it('settings failure + row snapshot (row.clinic_name) → the row brand still prints', async () => {
    fetchClinicSettingsMock.mockRejectedValue(new Error('network down'));
    const html = await buildPanelTicketPrintableHtml({ queue_number: 22, clinic_name: 'Doktor KosMed' });
    expect(html).toContain('Doktor KosMed');
    expect(html).not.toContain('Programma Clinic');
  });

  it('fulfilled settings → the configured clinic name prints (unchanged happy path)', async () => {
    const html = await buildPanelTicketPrintableHtml({ queue_number: 23 });
    expect(html).toContain('City Clinic');
  });

  it('payload-level resolveClinicName has no Programma fallback (no foreign default anywhere)', async () => {
    fetchClinicSettingsMock.mockRejectedValue(new Error('offline'));
    // Даже payload без clinic_name не получает чужое имя.
    const payload = buildPanelTicketPayload({ queue_number: 24 });
    expect(payload.clinic_name ?? '').toBe('');
  });
});

describe('CSH-FE-043 — the unconditional-true sync wrapper is gone', () => {
  it('module no longer exports printPanelTicketInBrowser', () => {
    expect((panelPrintModule as Record<string, unknown>).printPanelTicketInBrowser).toBeUndefined();
  });
});

describe('CSH-FE-044 — ticket/receipt print outcomes are honest', () => {
  it('ticket: print() throws → success: false (caller can recover)', async () => {
    const win = makeFakeWindow({
      readyState: 'complete',
      printImpl: () => {
        throw new Error('print preview disabled');
      },
    });
    window.open = vi.fn(() => win);

    const result = await printPanelTicketInBrowserAsync({ queue_number: 25 });
    expect(result.opened).toBe(true);
    // Прежде: success был true всегда (обёртка finalize возвращала true).
    expect(result.success).toBe(false);
  });

  it('ticket: print() succeeds → success: true', async () => {
    const win = makeFakeWindow();
    window.open = vi.fn(() => win);

    const result = await printPanelTicketInBrowserAsync({ queue_number: 26 });
    expect(result).toEqual({ opened: true, success: true });
  });

  it('ticket: popup blocked → opened: false (the caller branch is now reachable)', async () => {
    window.open = vi.fn(() => null);
    const result = await printPanelTicketInBrowserAsync({ queue_number: 27 });
    expect(result.opened).toBe(false);
  });

  it('receipt: returns the typed PrintableWindowResult (not a boolean lie)', () => {
    const win = makeFakeWindow({
      readyState: 'complete',
      printImpl: () => {
        throw new Error('not available');
      },
    });
    window.open = vi.fn(() => win);

    const outcome = printPanelReceiptInBrowser({ payment: { id: 5 }, patient: {}, services: [] });
    expect(outcome).toEqual({ opened: true, printInvoked: false, deferred: false });
  });
});

describe('CSH-FE-045 — batch printing opens ONE window in the gesture, then fills it', () => {
  it('openPanelTicketBatchWindow: window.open synchronously + placeholder written', () => {
    const win = makeFakeWindow();
    window.open = vi.fn(() => win);

    const batchWindow = openPanelTicketBatchWindow();
    expect(batchWindow).toBe(win);
    expect(window.open).toHaveBeenCalledTimes(1);
    expect(win.document.write).toHaveBeenCalledWith(expect.stringContaining('Подготовка талонов к печати'));
  });

  it('openPanelTicketBatchWindow: blocked → null (no silent batch)', () => {
    window.open = vi.fn(() => null);
    expect(openPanelTicketBatchWindow()).toBeNull();
  });

  it('buildPanelTicketsBatchPrintableHtml: one document carries every ticket in order', async () => {
    const html = await buildPanelTicketsBatchPrintableHtml([
      { queue_number: 31, patient_name: 'AAA' },
      { queue_number: 32, patient_name: 'BBB' },
    ]);
    expect(html).toContain('№31');
    expect(html).toContain('№32');
    expect(html.indexOf('№31')).toBeLessThan(html.indexOf('№32'));
    // Один документ: ровно один <html> заголовок на весь пакет.
    expect((html.match(/<html>/g) || []).length).toBe(1);
  });

  it('buildPanelTicketsBatchPrintableHtml: empty list is an honest error', async () => {
    await expect(buildPanelTicketsBatchPrintableHtml([])).rejects.toThrow(/список талонов пуст/i);
  });

  it('printPanelTicketsBatchInExistingWindow: fills the pre-opened window; honest outcome', async () => {
    const win = makeFakeWindow();
    const result = await printPanelTicketsBatchInExistingWindow(win, [
      { queue_number: 33 },
      { queue_number: 34 },
    ]);
    expect(result).toEqual({ opened: true, success: true });
    expect(win.document.write).toHaveBeenCalledWith(expect.stringContaining('№33'));
  });

  it('printPanelTicketsBatchInExistingWindow: print() throws → success: false', async () => {
    const win = makeFakeWindow({
      printImpl: () => {
        throw new Error('no print');
      },
    });
    const result = await printPanelTicketsBatchInExistingWindow(win, [{ queue_number: 35 }]);
    expect(result.success).toBe(false);
  });

  it('printPanelTicketsBatchInExistingWindow: no window → opened: false', async () => {
    const result = await printPanelTicketsBatchInExistingWindow(null, [{ queue_number: 36 }]);
    expect(result.opened).toBe(false);
  });
});
