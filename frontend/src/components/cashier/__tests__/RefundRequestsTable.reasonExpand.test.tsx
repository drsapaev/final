/**
 * CSH-FE-049 (follow-up audit 2026-11-02): полная причина возврата доступна
 * КЛАВИАТУРНО.
 *
 * Прежше: ellipsized span (max-width:220px) с hover-title на НЕфокусируемом
 * элементе — sighted keyboard-only сотрудник не мог прочесть полное
 * обоснование перед одобрением/отказом по возврату.
 *
 * Red-first: на префиксном коде кнопки-переключателя не существовало —
 * до полного текста можно было добраться только мышью (native title).
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

import { buildRefundRequestColumns } from '../refundRequestsColumns';

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

const renderReasonCell = (reason: unknown) => {
  const columns = buildRefundRequestColumns(t, null, {
    handleApprove: vi.fn(),
    handleReject: vi.fn(),
    handleComplete: vi.fn(),
  });
  const reasonColumn = columns.find((column) => column.key === 'reason');
  expect(reasonColumn).toBeTruthy();
  // DataTableColumn.render — контракт колонки (3 аргумента: value, row, index).
  const renderCell = (reasonColumn as unknown as { render?: (v: unknown, r: unknown, i: number) => React.ReactNode }).render as (v: unknown, r: unknown, i: number) => React.ReactNode;
  expect(typeof renderCell).toBe('function');
  return render(<div>{renderCell(reason, {}, 0)}</div>);
};

describe('CSH-FE-049: keyboard-operable full refund reason', () => {
  it('long reason renders a FOCUSABLE toggle button with aria-expanded/aria-controls', () => {
    renderReasonCell('Пациент опоздал на приём более чем на 20 минут, врач принял решение о возврате средств за консультацию в полном объёме');
    const toggle = screen.getByTestId('refund-reason-toggle');
    expect(toggle.tagName).toBe('BUTTON');
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(toggle.getAttribute('aria-controls')).toBeTruthy();
    // Кнопка имеет осмысленную aria-метку (фокусируема + озвучиваема).
    expect(toggle.textContent).toContain('misc.rrt_reason_expand');
  });

  it('Tab-reachable button toggles the expanded state (wrap instead of clip)', () => {
    renderReasonCell('Длинная причина возврата, которая раньше была доступна только через hover-title на нефокусируемом span');
    const toggle = screen.getByTestId('refund-reason-toggle');
    const cell = screen.getByTestId('refund-cell-reason');

    expect(cell.className).not.toContain('refund-cell-reason--expanded');
    fireEvent.click(toggle);
    expect(cell.className).toContain('refund-cell-reason--expanded');
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    // Повторный клик сворачивает обратно (постоянный доступ, не one-shot).
    fireEvent.click(toggle);
    expect(cell.className).not.toContain('refund-cell-reason--expanded');
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
  });

  it('short reason needs no toggle (compact rows stay quiet)', () => {
    renderReasonCell('Дубль платежа');
    expect(screen.queryByTestId('refund-reason-toggle')).toBeNull();
    expect(screen.getByText('Дубль платежа')).toBeTruthy();
  });

  it('missing reason renders the honest dash without a toggle', () => {
    renderReasonCell(null);
    expect(screen.getByText('—')).toBeTruthy();
    expect(screen.queryByTestId('refund-reason-toggle')).toBeNull();
  });
});
