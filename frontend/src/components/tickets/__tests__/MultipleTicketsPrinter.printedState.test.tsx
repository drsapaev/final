/**
 * QUEUEPRINT-FE-001 + QUEUEPRINT-FE-002 (audit group97, 2026-11-15):
 * printed-state integrity of the multiple-tickets printer.
 *
 * Red-first (до фикса): printSingleTicket never updated printedTickets —
 * an individually printed ticket stayed visually unprinted and was included
 * again by «Печать всех» (duplicate print ops); the printed-state identity
 * was the SHARED queue_id, so same-queue tickets ({queue_id:17,n:4}/{...n:5})
 * collided into one Set entry (allPrinted=false, hasUnprinted=false at once)
 * and a new same-queue ticket could be silently treated printed.
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
  openPanelTicketBatchWindow,
  printPanelTicketInBrowserAsync,
  printPanelTicketsBatchInExistingWindow,
} from '../../../services/panelPrint';

const batchOpenMock = openPanelTicketBatchWindow as unknown as ReturnType<typeof vi.fn>;
const batchFillMock = printPanelTicketsBatchInExistingWindow as unknown as ReturnType<typeof vi.fn>;
const singlePrintMock = printPanelTicketInBrowserAsync as unknown as ReturnType<typeof vi.fn>;

const fakeWindow = { document: { write: vi.fn() } } as unknown as Window;

const advanceCountdownToEnd = async (seconds = 8) => {
  for (let i = 0; i < seconds; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
  }
};

const printedCardCount = (container: HTMLElement) =>
  container.querySelectorAll('.ticket-card.printed').length;

const singlePrintButtons = () =>
  screen
    .getAllByRole('button')
    .filter((b) => b.className.includes('print-single-btn'));

beforeEach(() => {
  vi.useFakeTimers();
  batchOpenMock.mockReset().mockReturnValue(fakeWindow);
  batchFillMock.mockReset().mockResolvedValue({ opened: true, success: true });
  singlePrintMock.mockReset().mockResolvedValue({ opened: true, success: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('MultipleTicketsPrinter — QUEUEPRINT-FE-001 single-print state', () => {
  it('successful single print marks THAT ticket printed and excludes it from the batch', async () => {
    const { container } = render(
      <MultipleTicketsPrinter
        tickets={[
          { queue_id: 'q1', queue_number: 11, patient_name: 'A' },
          { queue_id: 'q2', queue_number: 12, patient_name: 'B' },
          { queue_id: 'q3', queue_number: 13, patient_name: 'C' },
        ]}
        onClose={() => {}}
      />,
    );

    fireEvent.click(singlePrintButtons()[0]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // Один успешный одиночный вывод — ровно одна карточка помечена.
    expect(singlePrintMock).toHaveBeenCalledTimes(1);
    expect(printedCardCount(container)).toBe(1);

    // Пакетная печать включает только ОСТАВШИЕСЯ талоны.
    fireEvent.click(screen.getByRole('button', { name: /Печать всех/ }));
    await advanceCountdownToEnd(7);
    expect(batchFillMock).toHaveBeenCalledTimes(1);
    const rows = batchFillMock.mock.calls[0][1];
    expect(rows).toHaveLength(2);
    expect(rows.map((r: { queue_number: unknown }) => r.queue_number)).toEqual([12, 13]);
  });

  it('failed single print leaves the ticket pending (invocation ≠ delivery)', async () => {
    singlePrintMock.mockResolvedValue({ opened: false, success: false });
    const { container } = render(
      <MultipleTicketsPrinter
        tickets={[
          { queue_id: 'q1', queue_number: 11, patient_name: 'A' },
          { queue_id: 'q2', queue_number: 12, patient_name: 'B' },
        ]}
        onClose={() => {}}
      />,
    );

    fireEvent.click(singlePrintButtons()[0]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // Провал вывода НЕ помечает талон напечатанным.
    expect(printedCardCount(container)).toBe(0);
    // Талон остаётся в пакетной очереди.
    fireEvent.click(screen.getByRole('button', { name: /Печать всех/ }));
    await advanceCountdownToEnd(7);
    expect(batchFillMock.mock.calls[0][1]).toHaveLength(2);
  });

  it('keeps batch printing disabled while a single ticket is preparing', async () => {
    singlePrintMock.mockImplementationOnce(async () => {
      await new Promise<void>((resolve) => setTimeout(resolve, 1000));
      return { opened: true, success: true };
    });
    render(<MultipleTicketsPrinter
      tickets={[{ queue_id: 17, queue_number: 4 }, { queue_id: 17, queue_number: 5 }]}
      onClose={() => {}}
    />);

    fireEvent.click(singlePrintButtons()[0]);
    const batchButton = screen.getByRole('button', { name: /Печать всех/ });
    expect(batchButton).toBeDisabled();
    fireEvent.click(batchButton);
    expect(batchOpenMock).not.toHaveBeenCalled();

    await advanceCountdownToEnd(1);
    expect(screen.getByRole('button', { name: 'Печать всех (1)' })).toBeEnabled();
  });
});

describe('MultipleTicketsPrinter — QUEUEPRINT-FE-002 per-ticket identity', () => {
  const sameQueueTickets = [
    { queue_id: 17, queue_number: 4, patient_name: 'D' },
    { queue_id: 17, queue_number: 5, patient_name: 'E' },
  ];

  it('same queue_id, different queue_number — single print marks exactly ONE card', async () => {
    const { container } = render(
      <MultipleTicketsPrinter tickets={sameQueueTickets} onClose={() => {}} />,
    );

    fireEvent.click(singlePrintButtons()[0]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(singlePrintMock).toHaveBeenCalledTimes(1);
    expect(printedCardCount(container)).toBe(1);
    // Вторая карточка той же очереди остаётся с кнопкой печати.
    expect(singlePrintButtons().length).toBe(1);

    // Пакетная догрузка включает только незапечатанный талон №5.
    fireEvent.click(screen.getByRole('button', { name: /Печать всех/ }));
    await advanceCountdownToEnd(7);
    const rows = batchFillMock.mock.calls[0][1];
    expect(rows).toHaveLength(1);
    expect(rows[0].queue_number).toBe(5);
  });

  it('batch completion marks BOTH same-queue tickets (consistent allPrinted/hasUnprinted)', async () => {
    const onAllPrinted = vi.fn();
    const { container } = render(
      <MultipleTicketsPrinter tickets={sameQueueTickets} onClose={() => {}} onAllPrinted={onAllPrinted} />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Печать всех/ }));
    await advanceCountdownToEnd(7);

    expect(batchFillMock).toHaveBeenCalledTimes(1);
    expect(batchFillMock.mock.calls[0][1]).toHaveLength(2);
    expect(printedCardCount(container)).toBe(2);
    expect(onAllPrinted).toHaveBeenCalledTimes(1);
    // Обе напечатаны: кнопка «Печать всех» исчезла (hasUnprinted=false).
    expect(screen.queryByRole('button', { name: /Печать всех/ })).toBeNull();
  });

  it('counts the pending tickets present after the list changes', async () => {
    const { rerender } = render(
      <MultipleTicketsPrinter tickets={sameQueueTickets} onClose={() => {}} />,
    );
    fireEvent.click(singlePrintButtons()[0]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    rerender(<MultipleTicketsPrinter tickets={[sameQueueTickets[1]]} onClose={() => {}} />);

    expect(screen.getByRole('button', { name: 'Печать всех (1)' })).toBeEnabled();
  });

  it('holds both print controls until an in-flight batch settles', async () => {
    batchFillMock.mockImplementationOnce(async () => {
      await new Promise<void>((resolve) => setTimeout(resolve, 1000));
      return { opened: true, success: false };
    });
    render(<MultipleTicketsPrinter tickets={sameQueueTickets} onClose={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: /Печать всех/ }));
    expect(singlePrintButtons()[0]).toBeDisabled();
    await advanceCountdownToEnd(5);
    expect(batchFillMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: /Печать всех/ })).toBeDisabled();
    expect(singlePrintButtons()[0]).toBeDisabled();
    expect(singlePrintMock).not.toHaveBeenCalled();

    await advanceCountdownToEnd(1);
    expect(screen.getByRole('button', { name: 'Печать всех (2)' })).toBeEnabled();
    expect(singlePrintButtons()[0]).toBeEnabled();
  });
});
