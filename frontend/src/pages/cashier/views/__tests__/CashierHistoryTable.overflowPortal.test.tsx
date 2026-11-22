/**
 * CSH-FE-046 / CSH-FE-047 (follow-up audit 2026-11-02): геометрия и
 * семантика ячейки действий истории платежей.
 *
 * 046: меню действий прежде было position:absolute внутри
 *      .cashier-table-scroll (overflow-x:auto ⇒ вычисляемый overflow-y:auto):
 *      поповер нижних строк обрезался скролл-предком. Теперь контент меню
 *      рендерится ПОРТАЛОМ в document.body (position:fixed + коллизия
 *      вьюпорта, свертывание вверх при нехватке места снизу).
 * 047: display:flex прежде назначался ПРЯМО на <td> (класс
 *      cashier-cell-actions на ячейке) — ячейка переставала быть
 *      table-cell. Теперь flex на внутреннем div, <td> нативен.
 *
 * Red-first (до фикса): поповер жил внутри скролл-контейнера; td имел
 * class=cashier-cell-actions с display:flex из CSS.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

import CashierHistoryTable from '../CashierHistoryTable';
import { ThemeProvider } from '../../../../contexts/ThemeContext';
import type { CashierPaymentRow } from '../../cashierPaymentContracts';

const tI18n = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

const mkRow = (id: number): CashierPaymentRow =>
  ({
    id,
    date: '03.11.2026',
    time: '14:00',
    patient: 'Patient X',
    service: 'Consultation',
    method: 'cash',
    total_amount: 100000,
    status: 'paid',
    available_actions: ['cancel', 'refund', 'print_receipt', 'confirm'],
    can_cancel: true,
    can_refund: true,
    can_print_receipt: true,
  }) as CashierPaymentRow;

const rows: CashierPaymentRow[] = [mkRow(1), mkRow(2), mkRow(3)];

const renderTable = () =>
  render(
    <ThemeProvider>
      <CashierHistoryTable
        historyLoading={false}
        historyError={null}
        filteredPayments={rows}
        sortField="date"
        sortDir="asc"
        onToggleSort={() => {}}
        confirmPayment={() => {}}
        openCancelDialog={() => {}}
        openRefundDialog={() => {}}
        handlePrintReceipt={() => {}}
        processingAction={null}
        currentPage={1}
        onCurrentPageChange={() => {}}
        totalPages={1}
        totalItems={rows.length}
        tI18n={tI18n}
      />
    </ThemeProvider>,
  );

beforeEach(() => {
  // jsdom getBoundingClientRect по умолчанию нулевой; задаём реальные
  // геометрии для сценария «нижняя строка» и триггера.
  Element.prototype.getBoundingClientRect = vi.fn(() => ({
    x: 900, y: 600, top: 600, bottom: 632, left: 900, right: 940,
    width: 40, height: 32, toJSON: () => ({}),
  }) as DOMRect);
  Object.defineProperty(window, 'innerWidth', { value: 1280, configurable: true });
  Object.defineProperty(window, 'innerHeight', { value: 768, configurable: true });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('CSH-FE-046 — overflow menu renders OUTSIDE the scroll container', () => {
  it('opening the LAST row menu portals the popover to document.body', async () => {
    const { container } = renderTable();

  const triggers = container.querySelectorAll('.cashier-overflow-menu summary');
  expect(triggers.length).toBe(3);
  // Открываем меню ПОСЛЕДНЕЙ строки (раньше оно обрезалось скролл-предком).
  fireEvent.click(triggers[triggers.length - 1]);
  // jsdom ставит open/toggle асинхронно — ждём портал.
  const popover = await screen.findByTestId('cashier-overflow-popover');
  // Портал: узел живёт в document.body, а НЕ внутри скролл-контейнера таблицы.
  expect(popover.closest('.cashier-table-scroll')).toBeNull();
  expect(document.body.contains(popover)).toBe(true);
  // Позиционирование — fixed (не absolute внутри предка).
  expect(popover.style.position).toBe('fixed');
});

  it('low trigger flips the popover UP (viewport collision)', async () => {
    // bottom=632; при высоте вьюпорта 740 места снизу 108 < 126+8 — флип вверх.
    Object.defineProperty(window, 'innerHeight', { value: 740, configurable: true });
    const { container } = renderTable();

    const triggers = container.querySelectorAll('.cashier-overflow-menu summary');
    fireEvent.click(triggers[0]);
    const popover = await screen.findByTestId('cashier-overflow-popover');
    expect(popover.style.position).toBe('fixed');
    // Свернуто вверх: верх поповера выше триггера (top 600).
    const top = Number.parseFloat(popover.style.top);
    expect(top).toBeLessThan(600);
    expect(top).toBeGreaterThan(0);
  });

  it('menu carries exactly the three backend-gated actions', async () => {
    const { container } = renderTable();
    fireEvent.click(container.querySelector('.cashier-overflow-menu summary') as Element);
    const popover = await screen.findByTestId('cashier-overflow-popover');
    const items = popover.querySelectorAll('[role="menuitem"]');
    expect(items.length).toBe(3);
  });
});

describe('CSH-FE-047 — actions td stays a native table cell', () => {
  it('td keeps semantic padding class; flex lives on the inner div', () => {
    const { container } = renderTable();
    const actionsCells = container.querySelectorAll('td.cashier-cell-actions');
    // Прежде: display:flex применялся ПРЯМО к <td>.
    expect(actionsCells.length).toBe(0);

    const tds = container.querySelectorAll('td.cashier-cell-padded');
    expect(tds.length).toBeGreaterThan(0);
    const innerFlexDivs = container.querySelectorAll('.cashier-cell-actions');
    expect(innerFlexDivs.length).toBe(3);
    // Внутренний div-обёртка внутри td — не наоборот.
    innerFlexDivs.forEach((div) => {
      expect(div.closest('td')).not.toBeNull();
    });
  });
});
