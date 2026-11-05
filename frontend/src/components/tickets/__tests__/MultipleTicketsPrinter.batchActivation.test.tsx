/**
 * CSH-FE-045 (follow-up audit 2026-11-02): пакетная печать талонов открывает
 * ОДНО окно синхронно в прямом жесте пользователя.
 *
 * Прежде: клик «Печать всех» запускал 5-секундный отсчёт, затем КАЖДЫЙ талон
 * открывал свой popup после 800мс паузы — окно открывалось на 5.8с позже
 * клика, вне окна доверенной активации, и блокировалось браузером.
 *
 * Red-first (до фикса): openPanelTicketBatchWindow не существовал; клик не
 * открывал окно синхронно; пакетная печать звала printPanelTicketInBrowserAsync
 * по разу на талон с паузами.
 */
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

vi.mock('../../../services/panelPrint', () => ({
  buildPanelTicketPayload: vi.fn((ticket: Record<string, unknown>) => ({ ...ticket })),
  printPanelTicketInBrowserAsync: vi.fn(async () => ({ opened: true, success: true })),
  openPanelTicketBatchWindow: vi.fn(),
  printPanelTicketsBatchInExistingWindow: vi.fn(async () => ({ opened: true, success: true })),
}));

import MultipleTicketsPrinter from '../MultipleTicketsPrinter';
import {
  buildPanelTicketPayload,
  openPanelTicketBatchWindow,
  printPanelTicketInBrowserAsync,
  printPanelTicketsBatchInExistingWindow,
} from '../../../services/panelPrint';

const batchOpenMock = openPanelTicketBatchWindow as unknown as ReturnType<typeof vi.fn>;
const batchFillMock = printPanelTicketsBatchInExistingWindow as unknown as ReturnType<typeof vi.fn>;
const singlePrintMock = printPanelTicketInBrowserAsync as unknown as ReturnType<typeof vi.fn>;
const buildPayloadMock = buildPanelTicketPayload as unknown as ReturnType<typeof vi.fn>;

const fakeWindow = { document: { write: vi.fn() } } as unknown as Window;

const tickets = [
  { queue_id: 'q1', queue_number: 11, patient_name: 'A' },
  { queue_id: 'q2', queue_number: 12, patient_name: 'B' },
  { queue_id: 'q3', queue_number: 13, patient_name: 'C' },
];

/**
 * Fake timers + React: один act() продвигает ОДНО звено цепочки
 * countdown (setState → effect → следующий таймер). Прокручиваем отсчёт
 * до конца шагами по 1с, как делает пользователь, ждущий 5 секунд.
 */
const advanceCountdownToEnd = async (seconds = 8) => {
  for (let i = 0; i < seconds; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
  }
};

beforeEach(() => {
  vi.useFakeTimers();
  batchOpenMock.mockReset().mockReturnValue(fakeWindow);
  batchFillMock.mockReset().mockResolvedValue({ opened: true, success: true });
  singlePrintMock.mockReset().mockResolvedValue({ opened: true, success: true });
  buildPayloadMock.mockReset().mockImplementation((t: Record<string, unknown>) => ({ ...t }));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('MultipleTicketsPrinter — CSH-FE-045 batch activation', () => {
  it('click «Печать всех» opens the batch window SYNCHRONOUSLY (same tick, no countdown delay)', () => {
    render(<MultipleTicketsPrinter tickets={tickets} onClose={() => {}} />);
    act(() => {
      vi.advanceTimersByTime(0);
    });

    fireEvent.click(screen.getByRole('button', { name: /Печать всех/ }));
    // Синхронно в жесте: вызов был в том же тике, что и клик.
    expect(batchOpenMock).toHaveBeenCalledTimes(1);
    // Отсчёт начался — кнопка заблокирована «Печать через Nс».
    expect(screen.getByText(/Печать через 5с/)).toBeTruthy();
  });

  it('blocked popup → honest error message, countdown does NOT start', () => {
    batchOpenMock.mockReturnValue(null);
    render(<MultipleTicketsPrinter tickets={tickets} onClose={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: /Печать всех/ }));
    expect(batchOpenMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('mtp-batch-error').textContent).toContain('заблокировал');
    // Раньше отсчёт стартовал всегда; теперь без окна отсчёт не начинается.
    expect(screen.queryByText(/Печать через/)).toBeNull();
    // Кнопка «Печать всех» остаётся пользователю как путь восстановления.
    expect(screen.getByRole('button', { name: /Печать всех/ })).toBeTruthy();
  });

  it('countdown to zero → ONE batch fill for ALL pending tickets (no per-ticket popups, no 800ms pauses)', async () => {
    const onAllPrinted = vi.fn();
    render(<MultipleTicketsPrinter tickets={tickets} onClose={() => {}} onAllPrinted={onAllPrinted} />);

    fireEvent.click(screen.getByRole('button', { name: /Печать всех/ }));
    // Окно открыто в жесте; отсчёт лишь задерживает печать (прежде 5с+3×800мс
    // открывали попапы ПОСЛЕ клика — вне окна активации).
    await advanceCountdownToEnd(7);

    expect(batchFillMock).toHaveBeenCalledTimes(1);
    const [windowArg, rowsArg] = batchFillMock.mock.calls[0];
    expect(windowArg).toBe(fakeWindow);
    expect(rowsArg).toHaveLength(3);
    expect(rowsArg.map((r: { queue_number: unknown }) => r.queue_number)).toEqual([11, 12, 13]);
    // Попап на каждый талон больше не открывается вовсе.
    expect(singlePrintMock).not.toHaveBeenCalled();
    expect(onAllPrinted).toHaveBeenCalledTimes(1);
  });

  it('batch failure → nothing is marked printed; honest error + retry stays', async () => {
    batchFillMock.mockResolvedValue({ opened: true, success: false, error: new Error('render failed') });
    const onAllPrinted = vi.fn();
    render(<MultipleTicketsPrinter tickets={tickets} onClose={() => {}} onAllPrinted={onAllPrinted} />);

    fireEvent.click(screen.getByRole('button', { name: /Печать всех/ }));
    await advanceCountdownToEnd(7);

    expect(batchFillMock).toHaveBeenCalledTimes(1);
    expect(onAllPrinted).not.toHaveBeenCalled();
    expect(screen.getByTestId('mtp-batch-error').textContent).toContain('Не удалось подготовить печать');
    // Кнопка остаётся: повтор возможен.
    expect(screen.getByRole('button', { name: /Печать всех/ })).toBeTruthy();
  });

  it('per-ticket button keeps the direct-gesture single print (unchanged)', async () => {
    render(<MultipleTicketsPrinter tickets={tickets} onClose={() => {}} />);

    // Кнопки «Печать» на карточках (класс print-single-btn; текст —
    // i18n-ключ, мок t() возвращает ключ как есть).
    const printButtons = screen
      .getAllByRole('button')
      .filter((b) => b.className.includes('print-single-btn'));
    expect(printButtons.length).toBeGreaterThan(0);
    fireEvent.click(printButtons[0]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(singlePrintMock).toHaveBeenCalledTimes(1);
    expect(batchOpenMock).not.toHaveBeenCalled();
  });
});
