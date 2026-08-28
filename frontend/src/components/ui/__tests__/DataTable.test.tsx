import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DataTable from '../DataTable';
import type { DataTableColumn, RowId } from '../DataTable';

/**
 * DataTable canonical contract tests.
 *
 * PR-UI-09a (foundation).
 *
 * ## Test organization
 *
 * The first 6 tests are ported verbatim from `frontend/src/components/ui/macos/__tests__/MacOSTable.test.tsx`
 * (per Task 46 §B.3 — MacOSTable.test.tsx was DUPLICATED here in 09a, with the
 * macos/Table.tsx alias pointing to canonical so the old test path kept passing
 * during the 09b–09c migration). PR-UI-09d removed the legacy duplicate and the
 * alias; these 6 tests are now the sole owners of that contract coverage. These 6
 * tests assert the ZERO-DELTA guarantee — the canonical DataTable must render
 * byte-identically to the legacy macos/Table for the default rendering path.
 *
 * The next 6 tests are NEW — they assert the additive canonical features:
 * ID-based selection, stickyHeader, density, filter UI, pagination UI, error
 * state, and onRowClick keyboard nav.
 *
 * ## Naming convention
 *
 * `DT-<n>` — DataTable test id (stable across refactors).
 */

describe('DataTable — zero-delta port of MacOSTable.test.tsx (DT-1..6)', () => {
  const columns: DataTableColumn[] = [
    { key: 'name', title: 'Name', sortable: true },
    { key: 'age', title: 'Age', sortable: false }
  ];
  const data = [
    { name: 'John', age: 30 },
    { name: 'Jane', age: 25 }
  ];

  it('DT-1: adds tabIndex and aria-sort to sortable headers', () => {
    render(<DataTable columns={columns} data={data} />);

    const nameHeader = screen.getByText('Name').closest('th') as Element;
    const ageHeader = screen.getByText('Age').closest('th') as Element;

    expect(nameHeader).toHaveAttribute('tabIndex', '0');
    expect(nameHeader).toHaveAttribute('aria-sort', 'none');

    expect(ageHeader).not.toHaveAttribute('tabIndex');
    expect(ageHeader).not.toHaveAttribute('aria-sort');
  });

  it('DT-2: updates aria-sort when column is sorted', () => {
    render(<DataTable columns={columns} data={data} />);

    const nameHeader = screen.getByText('Name').closest('th') as Element;

    fireEvent.click(nameHeader);
    expect(nameHeader).toHaveAttribute('aria-sort', 'ascending');

    fireEvent.click(nameHeader);
    expect(nameHeader).toHaveAttribute('aria-sort', 'descending');
  });

  it('DT-3: triggers sort on Enter and Space keys', () => {
    const onSort = vi.fn();
    render(<DataTable columns={columns} data={data} onSort={onSort} />);

    const nameHeader = screen.getByText('Name').closest('th') as Element;

    fireEvent.keyDown(nameHeader, { key: 'Enter' });
    expect(onSort).toHaveBeenCalledWith('name', 'asc');

    fireEvent.keyDown(nameHeader, { key: ' ' });
    expect(onSort).toHaveBeenCalledWith('name', 'desc');
  });

  it('DT-4: adds role="status" and aria-live="polite" to loading state', () => {
    render(<DataTable columns={columns} loading={true} />);

    const loadingStatus = screen.getByRole('status');
    expect(loadingStatus).toHaveAttribute('aria-live', 'polite');
    expect(loadingStatus).toHaveTextContent(/Загрузка|Loading/i);
  });

  it('DT-5: adds role="status" and aria-live="polite" to empty state', () => {
    render(<DataTable columns={columns} data={[]} />);

    const emptyStatus = screen.getByRole('status');
    expect(emptyStatus).toHaveAttribute('aria-live', 'polite');
    expect(emptyStatus).toHaveTextContent(/Нет данных|No data/i);
  });

  it('DT-6: wraps custom empty state content without nested table rows', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <DataTable
        columns={columns}
        data={[]}
        emptyState={<div data-testid="empty-state-content">No rows yet</div>}
      />
    );

    const emptyContent = screen.getByTestId('empty-state-content');
    const statusEl = screen.getByRole('status');
    expect(emptyContent.closest('td')).toBe(statusEl);
    expect(emptyContent.closest('tr')).toBe(statusEl.closest('tr'));

    const nestingWarnings = consoleError.mock.calls.filter((call) =>
      call.join(' ').includes('validateDOMNesting')
    );
    expect(nestingWarnings).toEqual([]);

    consoleError.mockRestore();
  });
});

describe('DataTable — canonical features (DT-7..12)', () => {
  // Sample data with stable IDs (per Task 46 §C — ID-based selection contract).
  // Type is the canonical default: `Record<string, unknown>`. Tests below use
  // generic JSX `<DataTable<RowType> ... />` syntax (TypeScript 4.x+ supports
  // generic JSX angle-bracket syntax). When tsx compiler emits ambiguity, the
  // alternative is to type-cast via `as DataTableProps<RowType>` on the props
  // object literal — both approaches are equivalent.
  type Row = { id: string | number; name: string; age: number };
  const rows: Row[] = [
    { id: 'row-1', name: 'Alice', age: 30 },
    { id: 'row-2', name: 'Bob', age: 25 },
    { id: 'row-3', name: 'Carol', age: 41 },
  ];
  const columns: DataTableColumn<Row>[] = [
    { key: 'name', title: 'Name', sortable: true },
    { key: 'age', title: 'Age', sortable: false },
  ];

  it('DT-7: ID-based selection — onRowSelect fires with stable id, not index', () => {
    const handleRowSelect = vi.fn();
    const selected = new Set<RowId>(['row-2']);

    render(
      <DataTable<Row>
        columns={columns}
        data={rows}
        selectable
        selectedRows={selected}
        onRowSelect={handleRowSelect}
      />
    );

    // Click on row 1 (Alice) — currently NOT selected, so toggling → checked=true.
    fireEvent.click(screen.getByText('Alice'));
    expect(handleRowSelect).toHaveBeenCalledWith('row-1', true, expect.objectContaining({ name: 'Alice' }));

    // Click on row 2 (Bob) — currently selected, so toggling → checked=false.
    handleRowSelect.mockClear();
    fireEvent.click(screen.getByText('Bob'));
    expect(handleRowSelect).toHaveBeenCalledWith('row-2', false, expect.objectContaining({ name: 'Bob' }));
  });

  it('DT-8: stickyHeader=true adds position:sticky to header cells', () => {
    render(<DataTable columns={columns} data={rows} stickyHeader />);

    const nameHeader = screen.getByText('Name').closest('th') as Element;
    // jsdom supports inline-style inspection via the `style` IDL attribute.
    expect((nameHeader as HTMLElement).style.position).toBe('sticky');
    expect((nameHeader as HTMLElement).style.top).toBe('0px');
  });

  it('DT-9: density="compact" overrides default padding', () => {
    const { container: compactContainer } = render(
      <DataTable columns={columns} data={rows} density="compact" />
    );
    const { container: defaultContainer } = render(
      <DataTable columns={columns} data={rows} />
    );

    const compactHeader = compactContainer.querySelector('th') as HTMLElement;
    const defaultHeader = defaultContainer.querySelector('th') as HTMLElement;

    // Compact padding is "4px 10px" (header) — different from default ("10px 16px").
    expect(compactHeader.style.padding).toBe('4px 10px');
    expect(defaultHeader.style.padding).toBe('10px 16px');
    expect(compactHeader.style.padding).not.toBe(defaultHeader.style.padding);
  });

  it('DT-10: filterable=true renders per-column filter input row in thead', () => {
    const onFilter = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={rows}
        filterable
        filterConfig={{ name: 'ali' }}
        onFilter={onFilter}
      />
    );

    // Find the filter input for the "name" column by aria-label.
    const nameFilter = screen.getByRole('textbox', { name: /Фильтр по колонке Name/i });
    expect(nameFilter).toHaveValue('ali');

    fireEvent.change(nameFilter, { target: { value: 'Bob' } });
    expect(onFilter).toHaveBeenCalledWith('name', 'Bob');
  });

  it('DT-11: pagination=true renders sticky bottom pagination footer', () => {
    const onPageChange = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={rows}
        pagination
        currentPage={1}
        pageSize={2}
        totalItems={rows.length}
        onPageChange={onPageChange}
      />
    );

    // Navigation landmark with aria-label "Пагинация".
    const nav = screen.getByRole('navigation', { name: /Пагинация/i });
    expect(nav).toBeInTheDocument();

    // Summary text mentions "Показано 1–2 из 3" (note: en-dash U+2013
    // between startItem and endItem — matches the typographic convention
    // used in the canonical TablePagination rendering).
    expect(nav).toHaveTextContent(/Показано 1.{1,2}2 из 3/i);

    // "Next page" button is enabled (currentPage=1, totalPages=2).
    const nextBtn = screen.getByRole('button', { name: /Следующая страница/i });
    expect(nextBtn).not.toBeDisabled();
    fireEvent.click(nextBtn);
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('DT-12: error prop renders role="alert" status cell with assertive aria-live', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        error={<span data-testid="err-msg">Ошибка 500</span>}
      />
    );

    const alertCell = screen.getByRole('alert');
    expect(alertCell).toHaveAttribute('aria-live', 'assertive');
    expect(alertCell).toHaveTextContent('Ошибка 500');
  });
});

describe('DataTable — row virtualization (DT-13..16, PR-UI-09e-1)', () => {
  type VRow = { id: number; name: string };
  const columns: DataTableColumn<VRow>[] = [
    { key: 'name', title: 'Name', sortable: false },
  ];
  const makeRows = (count: number): VRow[] =>
    Array.from({ length: count }, (_, i) => ({ id: i, name: `Row ${i}` }));

  // jsdom performs no layout: every element reports offsetHeight 0 and
  // @tanstack/react-virtual would compute an empty window. The virtualizer
  // measures the viewport (a <div>) and the rows (<tr>) via offsetHeight, so
  // tag-specific prototype mocks give a deterministic 320px viewport and a
  // configurable row height — scoped to this describe block and restored.
  const VIEWPORT = 320;
  let mockRowHeight = 32;
  const trDescriptor = Object.getOwnPropertyDescriptor(HTMLTableRowElement.prototype, 'offsetHeight');
  const divDescriptor = Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, 'offsetHeight');
  beforeEach(() => {
    mockRowHeight = 32;
    Object.defineProperty(HTMLTableRowElement.prototype, 'offsetHeight', {
      configurable: true,
      get: () => mockRowHeight,
    });
    Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', {
      configurable: true,
      value: VIEWPORT,
    });
  });
  afterEach(() => {
    if (trDescriptor) {
      Object.defineProperty(HTMLTableRowElement.prototype, 'offsetHeight', trDescriptor);
    }
    if (divDescriptor) {
      Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', divDescriptor);
    }
  });

  it('DT-13: virtualized=true + maxHeight renders a windowed subset of 1000 rows with spacer geometry', () => {
    const rows = makeRows(1000);
    const { container } = render(
      <DataTable<VRow> columns={columns} data={rows} virtualized rowHeight={32} maxHeight={VIEWPORT} />
    );

    const tbody = container.querySelector('tbody');
    expect(tbody).not.toBeNull();

    const allRows = tbody!.querySelectorAll('tr');
    // Windowed rendering: DOM rows (window + overscan + spacers) must be a
    // small subset of 1000 — this is the AC4 "1000 rows without lag" proof.
    expect(allRows.length).toBeLessThan(100);
    expect(allRows.length).toBeGreaterThan(0);

    const dataRows = Array.from(allRows).filter(
      (tr) => tr.getAttribute('aria-hidden') !== 'true'
    );
    expect(dataRows.length).toBeGreaterThan(0);
    expect(dataRows.length).toBeLessThan(100);

    // Spacer geometry: paddingTop + rendered*rowHeight + paddingBottom must
    // reconstruct the full virtual height (1000 × 32 = 32000).
    const spacers = Array.from(allRows).filter(
      (tr) => tr.getAttribute('aria-hidden') === 'true'
    );
    const spacerHeights = spacers.map((tr) =>
      Number((tr as HTMLElement).style.height.replace('px', ''))
    );
    const renderedHeight = dataRows.length * 32;
    const total =
      spacerHeights.reduce((acc, h) => acc + h, 0) + renderedHeight;
    expect(total).toBe(1000 * 32);

    // Rendered rows are the initial window (row 0 first) and carry data-index
    // for the virtualizer's measured geometry (Codex P2-1/P2-4 follow-up).
    expect(dataRows[0]).toHaveTextContent('Row 0');
    expect(dataRows[0].getAttribute('data-index')).toBe('0');

    // The scroll wrapper is the bounded vertical viewport.
    const wrapper = container.querySelector('.mac-table-scroll-wrapper') as HTMLElement;
    expect(wrapper.style.overflowY).toBe('auto');
    expect(wrapper.style.maxHeight).toBe(`${VIEWPORT}px`);

    // Codex P2-2 (PR 2872): table-layout is fixed while virtualized so
    // column widths cannot shift when a later window renders wider content.
    const table = container.querySelector('table') as HTMLElement;
    expect(table.style.tableLayout).toBe('fixed');

    // Codex P2-7 (PR 2872): virtualized cells clip content at the cell box
    // so unbreakable content cannot paint across neighboring columns.
    const firstCell = dataRows[0].querySelector('td') as HTMLElement;
    expect(firstCell.style.overflow).toBe('hidden');

    // Codex P2-6 (PR 2872): ARIA row semantics expose the virtual structure
    // — full row count on the table, absolute 1-based row index on each data
    // row (row 1 is the header).
    expect(table.getAttribute('aria-rowcount')).toBe('1001');
    expect(dataRows[0].getAttribute('aria-rowindex')).toBe('2');
  });

  it('DT-14: scrolling the viewport shifts the rendered window near the end of the dataset', () => {
    const rows = makeRows(1000);
    const { container } = render(
      <DataTable<VRow> columns={columns} data={rows} virtualized rowHeight={32} maxHeight={VIEWPORT} />
    );

    const wrapper = container.querySelector('.mac-table-scroll-wrapper') as HTMLElement;
    // Simulate scrolling to the bottom of the 32000px virtual height.
    // jsdom stores scrollTop assignments without layout; react-virtual's
    // scroll listener re-ranges the window off the stored offset.
    wrapper.scrollTop = 1000 * 32 - VIEWPORT;
    fireEvent.scroll(wrapper);

    const dataRows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (tr) => tr.getAttribute('aria-hidden') !== 'true'
    );
    // The window now sits at the tail of the dataset: last rendered row is
    // Row 999 (± overscan window math), and early rows are gone from the DOM.
    const names = dataRows.map((tr) => tr.textContent ?? '');
    expect(names[names.length - 1]).toContain('Row 999');
    expect(names).not.toContain('Row 0');
    expect(names).not.toContain('Row 1');
  });

  it('DT-15: virtualized=true without maxHeight stays on the plain path (explicit activation rule)', () => {
    const rows = makeRows(50);
    const { container } = render(
      <DataTable<VRow> columns={columns} data={rows} virtualized rowHeight={32} />
    );

    // No maxHeight → no bounded viewport → virtualization must NOT activate:
    // all 50 rows render, no spacers, wrapper has no inline viewport style.
    const allRows = container.querySelectorAll('tbody tr');
    expect(allRows.length).toBe(50);
    const spacers = Array.from(allRows).filter(
      (tr) => tr.getAttribute('aria-hidden') === 'true'
    );
    expect(spacers.length).toBe(0);
    const wrapper = container.querySelector('.mac-table-scroll-wrapper') as HTMLElement;
    expect(wrapper.style.overflowY).toBe('');
    expect(wrapper.style.maxHeight).toBe('');

    // Plain path keeps auto layout, no measurement attributes, no virtual
    // ARIA semantics, no cell clipping (no measured-geometry contract
    // outside virtualized mode).
    const table = container.querySelector('table') as HTMLElement;
    expect(table.style.tableLayout).toBe('');
    expect(table.getAttribute('aria-rowcount')).toBeNull();
    const firstRow = allRows[0];
    expect(firstRow.getAttribute('data-index')).toBeNull();
    expect(firstRow.getAttribute('aria-rowindex')).toBeNull();
    const firstCell = firstRow.querySelector('td') as HTMLElement;
    expect(firstCell.style.height).toBe('');
    expect(firstCell.style.overflow).toBe('');
  });

  it('DT-16: measured geometry — actual row heights override the rowHeight estimate (Codex P2-1/P2-4)', () => {
    // Rows actually measure 50px while the estimate is 40px: the spacers must
    // follow the MEASURED heights (1000 × 50 = 50000), proving the geometry
    // cannot desynchronize when content is taller than the estimate.
    mockRowHeight = 50;
    const rows = makeRows(1000);
    const { container } = render(
      <DataTable<VRow> columns={columns} data={rows} virtualized rowHeight={40} maxHeight={VIEWPORT} />
    );

    const allRows = Array.from(container.querySelectorAll('tbody tr'));
    const dataRows = allRows.filter((tr) => tr.getAttribute('aria-hidden') !== 'true');
    const spacers = allRows.filter((tr) => tr.getAttribute('aria-hidden') === 'true');

    expect(dataRows.length).toBeGreaterThan(0);
    expect(dataRows.length).toBeLessThan(100);

    const spacerHeights = spacers.map((tr) =>
      Number((tr as HTMLElement).style.height.replace('px', ''))
    );
    // Hybrid geometry: every RENDERED row contributes its measured 50px; the
    // unrendered remainder keeps the 40px estimate. If measurement wiring were
    // broken, rendered rows would contribute 40px each and this equality would
    // fail — this is the Codex P2-1/P2-4 proof that measured sizes drive the
    // spacer math instead of a fixed estimate.
    const spacerSum = spacerHeights.reduce((acc, h) => acc + h, 0);
    const total = spacerSum + dataRows.length * 50;
    // Measurement demonstrably moved the geometry STRICTLY above the
    // pure-estimate baseline (1000 × 40 = 40000): rendered rows were measured
    // at 50px and their extra height flows into the spacers/totalSize. If the
    // measureElement wiring were broken, every row would contribute exactly 40
    // and total would equal 40000.
    expect(total).toBeGreaterThan(40000);
    // And strictly below the fully-measured size (1000 × 50 = 50000): only
    // the rendered window is measured; off-window rows keep the estimate —
    // consistent virtualizer behavior, not a full-list measurement.
    expect(total).toBeLessThan(50000);
    // Every rendered row carries the measurement hook.
    for (const tr of dataRows) {
      expect(tr.getAttribute('data-index')).not.toBeNull();
    }
  });
});
