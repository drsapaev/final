/**
 * CSH-FE-046/047/048/049 (follow-up audit 2026-11-02): CSS-контракты
 * кассирных поверхностей.
 *
 * 046: .cashier-overflow-popover больше НЕ позиционируется absolute внутри
 *      скролл-предка (overflow-x:auto ⇒ вычисляемый overflow-y:auto клиппинг
 *      нижних строк) — позиционирование уходит инлайном в fixed из портала.
 * 047: display:flex больше НЕ назначается directly на <td>: класс
 *      cashier-cell-actions теперь применяется к внутреннему div.
 * 048: .cashier-pagination переносится (wrap) — прежде неразрывный flex-ряд
 *      двух кнопок и длинной localized-строки уходил за край.
 * 049: раскрытая причина возврата переносится по строкам (--expanded).
 *
 * Source-contract тест (прецедент репо: EnhancedAppointmentsTable.cssContract).
 * Red-first: все паттерны присутствовали в префиксном CSS.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = path.dirname(fileURLToPath(import.meta.url));
const cashierCss = fs.readFileSync(path.resolve(here, '../cashier.css'), 'utf-8').replace(/\r\n/g, '\n');
const refundCss = fs.readFileSync(
  path.resolve(here, '../../components/cashier/RefundRequestsTable.css'),
  'utf-8',
).replace(/\r\n/g, '\n');

const extractBlock = (source: string, selector: string): string => {
  const start = source.indexOf(selector);
  expect(start, `selector not found: ${selector}`).toBeGreaterThanOrEqual(0);
  const end = source.indexOf('}', start);
  return source.slice(start, end);
};

describe('CSH-FE-046: popover is no longer absolutely positioned inside the scrollport', () => {
  it('.cashier-overflow-popover has no position/top/right of its own', () => {
    const block = extractBlock(cashierCss, '.cashier-overflow-popover {');
    expect(block).not.toMatch(/position\s*:\s*absolute/);
    expect(block).not.toMatch(/top\s*:/);
    expect(block).not.toMatch(/right\s*:/);
    // Позиционирование (fixed) задаётся инлайном из OverflowMenuPortal.
    expect(block).toMatch(/min-width\s*:\s*200px/);
  });

  it('the scroll wrapper keeps horizontal scrolling (unchanged table UX)', () => {
    const block = extractBlock(cashierCss, '.cashier-table-scroll {');
    expect(block).toMatch(/overflow-x\s*:\s*auto/);
  });
});

describe('CSH-FE-047: flex no longer overrides the native td display', () => {
  it('.cashier-cell-actions keeps its flex contract (now on the inner div)', () => {
    const block = extractBlock(cashierCss, '.cashier-cell-actions {');
    expect(block).toMatch(/display\s*:\s*flex/);
    expect(block).toMatch(/flex-wrap\s*:\s*wrap/);
  });

  it('the padded cell class exists (td uses it instead of the flex class)', () => {
    const block = extractBlock(cashierCss, '.cashier-cell-padded {');
    expect(block).toMatch(/padding/);
    expect(block).not.toMatch(/display\s*:\s*flex/);
  });
});

describe('CSH-FE-048: pagination wraps on narrow viewports', () => {
  it('.cashier-pagination has flex-wrap and a row gap', () => {
    const block = extractBlock(cashierCss, '.cashier-pagination {');
    expect(block).toMatch(/flex-wrap\s*:\s*wrap/);
    expect(block).toMatch(/row-gap/);
    expect(block).toMatch(/justify-content\s*:\s*center/);
  });
});

describe('CSH-FE-049: expanded refund reason wraps instead of clipping', () => {
  it('.refund-cell-reason--expanded overrides nowrap with normal wrapping', () => {
    const block = extractBlock(refundCss, '.refund-cell-reason--expanded {');
    expect(block).toMatch(/white-space\s*:\s*normal/);
    expect(block).toMatch(/overflow-wrap\s*:\s*anywhere/);
  });

  it('the base .refund-cell-reason still ellipsizes (compact table rows)', () => {
    const block = extractBlock(refundCss, '.refund-cell-reason {');
    expect(block).toMatch(/white-space\s*:\s*nowrap/);
    expect(block).toMatch(/text-overflow\s*:\s*ellipsis/);
  });

  it('the focusable toggle button style exists', () => {
    const block = extractBlock(refundCss, '.refund-reason-toggle {');
    expect(block).toMatch(/cursor\s*:\s*pointer/);
  });
});
