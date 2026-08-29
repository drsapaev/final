import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
    // jsdom inherits offsetHeight from HTMLElement.prototype, so the captured
    // descriptors are undefined (Codex P2-8, PR 2872): restoring would be a
    // no-op and the mocks would leak into later test files in the shared
    // single-fork environment. When no own property existed, DELETE the mock
    // so lookup falls back to the real inherited getter.
    if (trDescriptor) {
      Object.defineProperty(HTMLTableRowElement.prototype, 'offsetHeight', trDescriptor);
    } else {
      delete (HTMLTableRowElement.prototype as { offsetHeight?: number }).offsetHeight;
    }
    if (divDescriptor) {
      Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', divDescriptor);
    } else {
      delete (HTMLDivElement.prototype as { offsetHeight?: number }).offsetHeight;
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

describe('DataTable — PR-UI-12 features (DT-17..27)', () => {
  type Row = { id: string | number; name: string; age: number; city: string };
  const columns: DataTableColumn<Row>[] = [
    { key: 'name', title: 'Name', sortable: true },
    { key: 'age', title: 'Age', sortable: false },
    { key: 'city', title: 'City', sortable: false }
  ];
  const rows: Row[] = [
    { id: 'r1', name: 'Alice', age: 30, city: 'Almaty' },
    { id: 'r2', name: 'Bob', age: 25, city: 'Berlin' },
    { id: 'r3', name: 'Carol', age: 35, city: 'Cairo' }
  ];

  const getRowByName = (name: string): HTMLTableRowElement =>
    screen.getByText(name).closest('tr') as HTMLTableRowElement;

  // --- DT-17..20: roving keyboard row navigation ---

  it('DT-17: keyboardNavigation=true gives rows a roving tabindex (active row 0, others -1)', () => {
    render(<DataTable columns={columns} data={rows} keyboardNavigation />);

    const first = getRowByName('Alice');
    const second = getRowByName('Bob');
    const third = getRowByName('Carol');
    expect(first).toHaveAttribute('tabIndex', '0');
    expect(second).toHaveAttribute('tabIndex', '-1');
    expect(third).toHaveAttribute('tabIndex', '-1');
    // Focus targeting attribute present only under keyboardNavigation.
    expect(first).toHaveAttribute('data-row-index', '0');
  });

  it('DT-17b: without keyboardNavigation rows keep the legacy tabIndex contract (zero-delta)', () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={columns} data={rows} onRowClick={onRowClick} />);

    // Interactive rows (onRowClick) all carry tabIndex 0 — byte-identical to
    // the pre-PR-UI-12 behavior; no roving, no data-row-index.
    expect(getRowByName('Alice')).toHaveAttribute('tabIndex', '0');
    expect(getRowByName('Bob')).toHaveAttribute('tabIndex', '0');
    expect(getRowByName('Alice')).not.toHaveAttribute('data-row-index');
  });

  it('DT-17c: keyboardNavigation without onRowClick still makes rows focusable', () => {
    render(<DataTable columns={columns} data={rows} keyboardNavigation />);
    // Roving focus works with no row action wired (QueueTable pattern).
    expect(getRowByName('Alice')).toHaveAttribute('tabIndex', '0');
    expect(getRowByName('Bob')).toHaveAttribute('tabIndex', '-1');
  });

  it('DT-18: ArrowDown moves roving focus to the next row', async () => {
    render(<DataTable columns={columns} data={rows} keyboardNavigation />);

    const first = getRowByName('Alice');
    const second = getRowByName('Bob');
    first.focus();
    fireEvent.keyDown(first, { key: 'ArrowDown' });

    // Roving tabindex moved.
    expect(first).toHaveAttribute('tabIndex', '-1');
    expect(second).toHaveAttribute('tabIndex', '0');
    // DOM focus followed (after the rAF hop — awaited via waitFor).
    await waitFor(() => expect(second).toHaveFocus());
  });

  it('DT-19: ArrowUp clamps at the first row; Home/End jump to bounds', async () => {
    render(<DataTable columns={columns} data={rows} keyboardNavigation />);

    const first = getRowByName('Alice');
    first.focus();
    fireEvent.keyDown(first, { key: 'ArrowUp' });
    expect(first).toHaveAttribute('tabIndex', '0');
    expect(first).toHaveFocus();

    fireEvent.keyDown(first, { key: 'End' });
    const last = getRowByName('Carol');
    expect(last).toHaveAttribute('tabIndex', '0');
    await waitFor(() => expect(last).toHaveFocus());

    fireEvent.keyDown(last, { key: 'Home' });
    expect(getRowByName('Alice')).toHaveAttribute('tabIndex', '0');
    await waitFor(() => expect(getRowByName('Alice')).toHaveFocus());
  });

  it('DT-20: Enter still activates onRowClick under keyboardNavigation', () => {
    const onRowClick = vi.fn();
    render(
      <DataTable columns={columns} data={rows} keyboardNavigation onRowClick={onRowClick} />
    );

    fireEvent.keyDown(getRowByName('Bob'), { key: 'Enter' });
    expect(onRowClick).toHaveBeenCalledTimes(1);
    expect(onRowClick).toHaveBeenCalledWith(rows[1], 1);
  });

  it('DT-20b: arrow keys do nothing without keyboardNavigation (zero-delta keyboard behavior)', () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={columns} data={rows} onRowClick={onRowClick} />);

    fireEvent.keyDown(getRowByName('Alice'), { key: 'ArrowDown' });
    // No roving movement: every row keeps tabIndex 0, focus did not move.
    expect(getRowByName('Alice')).toHaveAttribute('tabIndex', '0');
    expect(getRowByName('Bob')).toHaveAttribute('tabIndex', '0');
    expect(getRowByName('Alice')).not.toHaveFocus();
  });

  // --- DT-21: sticky filter row ---

  it('DT-21: stickyHeader + filterable — filter row cells stick below the header row', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        stickyHeader
        filterable
        onFilter={vi.fn()}
      />
    );

    const headerCells = screen.getAllByText('Name').map((el) => el.closest('th') as HTMLElement);
    const headerTh = headerCells[0] as HTMLElement;
    // The header cell itself is sticky at top 0.
    expect(headerTh.style.position).toBe('sticky');
    expect(headerTh.style.top).toBe('0px');

    // The filter input lives in the SECOND row of thead; its th is sticky too,
    // but with a MEASURED offset (jsdom reports offsetHeight 0 → '0px'; the
    // point under test is that the filter row carries its own sticky style
    // derived from filterStyleFinal, not the header row's top: 0 constant).
    const filterInput = screen.getByLabelText('Фильтр по колонке Name');
    const filterTh = filterInput.closest('th') as HTMLElement;
    expect(filterTh.style.position).toBe('sticky');
    expect(filterTh.style.top).toBe('0px'); // measured height in jsdom = 0
    // Both rows are in thead, filter strictly after the header row.
    const thead = filterTh.closest('thead') as HTMLElement;
    const headerRows = thead.querySelectorAll('tr');
    expect(headerRows.length).toBe(2);
  });

  it('DT-21b: filterable without stickyHeader keeps the non-sticky filter row (zero-delta)', () => {
    render(<DataTable columns={columns} data={rows} filterable onFilter={vi.fn()} />);

    const filterInput = screen.getByLabelText('Фильтр по колонке Name');
    const filterTh = filterInput.closest('th') as HTMLElement;
    expect(filterTh.style.position).toBe('');
  });

  // --- DT-22..23: column visibility ---

  it('DT-22: columnVisibility hides a column from headers, cells and empty-state colSpan', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        columnVisibility={{ age: false }}
      />
    );

    expect(screen.queryByText('Age')).toBeNull();
    expect(screen.queryByText('25')).toBeNull();
    expect(screen.getByText('City')).toBeInTheDocument();

    // Empty-state colSpan counts VISIBLE columns only.
    const { unmount } = render(
      <DataTable columns={columns} data={[]} columnVisibility={{ age: false, city: false }} />
    );
    const statusCell = screen.getByRole('status').closest('td') as HTMLElement;
    expect(statusCell).toHaveAttribute('colspan', '1');
    unmount();
  });

  it('DT-22b: static column.hidden is honored (previously inert prop)', () => {
    render(
      <DataTable
        columns={[...columns, { key: 'secret', title: 'Secret', hidden: true }]}
        data={rows}
      />
    );
    expect(screen.queryByText('Secret')).toBeNull();
    expect(screen.getByText('Name')).toBeInTheDocument();
  });

  it('DT-23: toolbar column toggle fires onColumnVisibilityChange with the next map', () => {
    const onColumnVisibilityChange = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        columnVisibility={{}}
        onColumnVisibilityChange={onColumnVisibilityChange}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Колонки|Columns/ }));
    const ageCheckbox = screen.getByLabelText('Age') as HTMLInputElement;
    fireEvent.click(ageCheckbox);

    expect(onColumnVisibilityChange).toHaveBeenCalledTimes(1);
    expect(onColumnVisibilityChange).toHaveBeenCalledWith({ age: false });
  });

  it('DT-24: showDensityToggle renders 3 options and fires onDensityChange', () => {
    const onDensityChange = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={rows}
        showDensityToggle
        density="comfortable"
        onDensityChange={onDensityChange}
      />
    );

    const group = screen.getByRole('group', { name: /Плотность|Row density|density/i });
    const options = group.querySelectorAll('button');
    expect(options.length).toBe(3);

    const comfortable = [...options].find((b) =>
      ['Стандарт', 'Comfortable'].includes(b.textContent || '')
    ) as HTMLButtonElement;
    expect(comfortable).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click([...options].find((b) => (b.textContent || '') === 'Компактно') as HTMLButtonElement);
    expect(onDensityChange).toHaveBeenCalledWith('compact');
  });

  it('DT-25: column menu opens, closes on Escape and on outside pointerdown', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        columnVisibility={{}}
        onColumnVisibilityChange={vi.fn()}
      />
    );

    const toggle = screen.getByRole('button', { name: /Колонки|Columns/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByLabelText('Age')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    // Outside pointerdown (a target outside the menu root) closes the menu.
    fireEvent.pointerDown(document.body);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('DT-26: the last visible column checkbox is disabled (a table needs at least one column)', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        columnVisibility={{ age: false, city: false }}
        onColumnVisibilityChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Колонки|Columns/ }));
    const nameCheckbox = screen.getByLabelText('Name') as HTMLInputElement;
    const ageCheckbox = screen.getByLabelText('Age') as HTMLInputElement;
    expect(nameCheckbox.disabled).toBe(true);
    expect(ageCheckbox.disabled).toBe(false);
  });

  it('DT-27: no toolbar props → no .mac-table-shell wrapper (zero-delta root)', () => {
    const { container } = render(<DataTable columns={columns} data={rows} />);
    expect(container.querySelector('.mac-table-shell')).toBeNull();
    expect(container.querySelector('.mac-table-toolbar')).toBeNull();
    // Root is still the plain scroll wrapper.
    expect(container.firstElementChild?.className).toContain('mac-table-scroll-wrapper');
  });

  // --- DT-29..31: Codex review fixes (PR 2885) ---

  it('DT-29: key events from embedded controls do not trigger row navigation (Codex P1)', () => {
    const onRowClick = vi.fn();
    render(
      <DataTable
        columns={[
          ...columns,
          {
            key: 'action',
            title: 'Action',
            render: () => (
              <button type="button" onClick={() => undefined}>
                Go
              </button>
            )
          }
        ]}
        data={rows}
        keyboardNavigation
        onRowClick={onRowClick}
      />
    );

    const first = getRowByName('Alice');
    first.focus();
    // The render fn places the button in every row; take the one inside row 1.
    const embeddedButton = screen.getAllByText('Go')[0];

    // ArrowDown bubbled from the embedded button: the row must NOT navigate
    // (roving tabindex unchanged, focus not moved) — the control keeps its keys.
    fireEvent.keyDown(embeddedButton, { key: 'ArrowDown', bubbles: true });
    expect(first).toHaveAttribute('tabIndex', '0');
    expect(getRowByName('Bob')).toHaveAttribute('tabIndex', '-1');

    // Enter bubbled from the embedded button: no row action fires (the
    // control's native activation is preserved, no double-activation).
    fireEvent.keyDown(embeddedButton, { key: 'Enter', bubbles: true });
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it('DT-30: Escape inside the column menu restores focus to the toggle button (Codex P2)', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        columnVisibility={{}}
        onColumnVisibilityChange={vi.fn()}
      />
    );

    const toggle = screen.getByRole('button', { name: /Колонки|Columns/ });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');

    // Keyboard user tabs into a menu checkbox, presses Escape.
    const ageCheckbox = screen.getByLabelText('Age') as HTMLInputElement;
    ageCheckbox.focus();
    fireEvent.keyDown(document, { key: 'Escape' });

    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(toggle).toHaveFocus();
  });

  it('DT-31: an externally supplied all-hidden visibility map falls back to visible columns (Codex P2)', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        columnVisibility={{ name: false, age: false, city: false }}
      />
    );

    // Degenerate map is normalized at the DataTable boundary: all statically
    // visible columns render (no headerless colSpan=0 table).
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('City')).toBeInTheDocument();
  });

  it('DT-27b: toolbar props wrap the table in .mac-table-shell above the scroll wrapper', () => {
    const { container } = render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        columnVisibility={{}}
        onColumnVisibilityChange={vi.fn()}
      />
    );
    const shell = container.querySelector('.mac-table-shell') as HTMLElement;
    expect(shell).not.toBeNull();
    expect(shell.querySelector('.mac-table-toolbar')).not.toBeNull();
    expect(shell.querySelector('.mac-table-scroll-wrapper')).not.toBeNull();
  });
  it('DT-32: all-hidden map + toolbar — checkboxes reflect the NORMALIZED state (Codex P2 #3)', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        columnVisibility={{ name: false, age: false, city: false }}
        onColumnVisibilityChange={vi.fn()}
      />
    );

    // All columns render (normalization) AND the menu shows every checkbox
    // CHECKED — renderer and toolbar share the post-normalization truth.
    expect(screen.getByText('Name')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Колонки|Columns/ }));
    expect((screen.getByLabelText('Name') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('Age') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('City') as HTMLInputElement).checked).toBe(true);
  });

  it('DT-33: interactive ReactNode column title renders as INERT key text in the menu (Codex P2)', () => {
    render(
      <DataTable
        columns={[
          {
            key: 'select',
            // Live control as header title — the FileManager/ServiceCatalog
            // select-all pattern.
            title: <input type="checkbox" aria-label="select-all" readOnly />,
            sortable: false
          },
          { key: 'name', title: 'Name', sortable: false }
        ]}
        data={rows}
        showColumnToggle
        columnVisibility={{}}
        onColumnVisibilityChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Колонки|Columns/ }));
    // The menu item is labeled by the INERT column key ('select'), not the
    // live checkbox node — no second interactive control inside the menu.
    const menuItem = screen.getByLabelText('select');
    expect(menuItem).toBeInTheDocument();
    expect(menuItem.tagName).toBe('INPUT');
    // Exactly ONE interactive 'select' control exists (the header title), the
    // menu item text is the plain key.
    expect(screen.getByText('select')).toBeInTheDocument();
  });

  it('DT-34: dataset shrink persists the roving-index clamp; regrowth does not snap back (Codex P2 #4)', () => {
    const { rerender } = render(<DataTable columns={columns} data={rows} keyboardNavigation />);

    // Move the roving tab stop to the last row (index 2).
    const first = getRowByName('Alice');
    fireEvent.keyDown(first, { key: 'End' });
    expect(getRowByName('Carol')).toHaveAttribute('tabIndex', '0');

    // Dataset shrinks to 1 row (filter/page/refresh): clamp persists.
    rerender(<DataTable columns={columns} data={[rows[0]]} keyboardNavigation />);
    expect(getRowByName('Alice')).toHaveAttribute('tabIndex', '0');

    // Dataset grows back: the tab stay stays clamped at 0 — it does NOT snap
    // back to the stale index 2.
    rerender(<DataTable columns={columns} data={rows} keyboardNavigation />);
    expect(getRowByName('Alice')).toHaveAttribute('tabIndex', '0');
    expect(getRowByName('Bob')).toHaveAttribute('tabIndex', '-1');
  });

  it('DT-35: toolbar toggle uses the disclosure pattern (aria-expanded + aria-controls, no aria-haspopup) (Codex P2)', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        columnVisibility={{}}
        onColumnVisibilityChange={vi.fn()}
      />
    );

    const toggle = screen.getByRole('button', { name: /Колонки|Columns/ });
    // The popup is a checkbox GROUP, not a menu — no aria-haspopup.
    expect(toggle).not.toHaveAttribute('aria-haspopup');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    const controlsId = toggle.getAttribute('aria-controls');
    expect(controlsId).toBeTruthy();

    // Opening mounts the controlled group with the matching id.
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const controlled = document.getElementById(controlsId as string);
    expect(controlled).not.toBeNull();
    expect(controlled).toHaveAttribute('role', 'group');
  });

  it('DT-36: every column statically hidden still renders one column (Codex P2 #5)', () => {
    render(
      <DataTable
        columns={[
          { key: 'a', title: 'A', hidden: true },
          { key: 'b', title: 'B', hidden: true }
        ]}
        data={rows}
      />
    );

    // Author-error guard: the first column renders so the ≥1-column invariant
    // holds (no headerless colSpan=0 table).
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.queryByText('B')).toBeNull();
  });

  it('DT-37: children composition path suppresses the toolbar entirely (Codex P2 round 4)', () => {
    const { container } = render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        showDensityToggle
        columnVisibility={{}}
        onColumnVisibilityChange={vi.fn()}
        onDensityChange={vi.fn()}
      >
        <tbody>
          <tr>
            <td>composed</td>
          </tr>
        </tbody>
      </DataTable>
    );

    // Composition mode: no toolbar shell, no toolbar — columnVisibility and
    // density cannot reach consumer-supplied children, so the controls must
    // not be advertised. Children render verbatim (zero-delta root).
    expect(container.querySelector('.mac-table-shell')).toBeNull();
    expect(container.querySelector('.mac-table-toolbar')).toBeNull();
    expect(container.querySelector('.mac-table-scroll-wrapper')).not.toBeNull();
    expect(screen.getByText('composed')).toBeInTheDocument();
  });

  it('DT-38: non-children paths keep the toolbar with both controls enabled', () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        showDensityToggle
        columnVisibility={{}}
        onColumnVisibilityChange={vi.fn()}
        onDensityChange={vi.fn()}
      />
    );
    expect(screen.getByRole('button', { name: /Колонки|Columns/ })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: /Плотность|density/i })).toBeInTheDocument();
  });

  it('DT-39: focus is restored to the clamped row when the focused row unmounts (Codex P2 round 5)', async () => {
    const { rerender } = render(<DataTable columns={columns} data={rows} keyboardNavigation />);

    // Focus the LAST row, then the dataset shrinks — the focused row unmounts
    // and the browser drops focus to <body>.
    const last = getRowByName('Carol');
    fireEvent.keyDown(getRowByName('Alice'), { key: 'End' });
    await waitFor(() => expect(last).toHaveFocus());

    rerender(<DataTable columns={columns} data={[rows[0]]} keyboardNavigation />);
    // Focus is restored to the clamped tab stop (row 0).
    await waitFor(() => expect(getRowByName('Alice')).toHaveFocus());
  });

  it('DT-40: hiding a column clears its active filter via onFilter (Codex P2 round 5)', () => {
    const onFilter = vi.fn();
    const onColumnVisibilityChange = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={rows}
        filterable
        filterConfig={{ name: 'Bo' }}
        onFilter={onFilter}
        showColumnToggle
        columnVisibility={{}}
        onColumnVisibilityChange={onColumnVisibilityChange}
      />
    );

    // Hide the 'name' column which carries a nonempty filter value.
    fireEvent.click(screen.getByRole('button', { name: /Колонки|Columns/ }));
    fireEvent.click(screen.getByLabelText('Name'));

    // The invisible filter is cleared through the existing onFilter contract,
    // and the visibility change is still propagated.
    expect(onFilter).toHaveBeenCalledWith('name', '');
    expect(onColumnVisibilityChange).toHaveBeenCalledWith({ name: false });
  });

  it('DT-41: virtualized window keeps a tab stop when the active row is off-window (Codex P2 round 6)', async () => {
    // jsdom performs no layout — mock the geometry (same pattern as DT-13..16;
    // scrollToIndex cannot drive the window here, so the window is moved by a
    // manual scrollTop assignment like DT-14).
    const trDescriptor = Object.getOwnPropertyDescriptor(HTMLTableRowElement.prototype, 'offsetHeight');
    const divDescriptor = Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, 'offsetHeight');
    Object.defineProperty(HTMLTableRowElement.prototype, 'offsetHeight', {
      configurable: true,
      get: () => 20
    });
    Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', {
      configurable: true,
      value: 200
    });
    try {
      const bigData = Array.from({ length: 200 }, (_, i) => ({
        id: `r${i}`,
        name: `Name ${i}`,
        age: 20 + i,
        city: `City ${i}`
      }));
      const { container } = render(
        <DataTable
          columns={columns}
          data={bigData}
          keyboardNavigation
          virtualized
          maxHeight={200}
          rowHeight={20}
        />
      );

      // Initial window at the top: the active row (0) is mounted and holds
      // the tab stop.
      const firstRow = screen.getByText('Name 0').closest('tr') as HTMLElement;
      expect(firstRow.getAttribute('tabIndex')).toBe('0');

      // Manually scroll to the tail: the active row (0) unmounts — every
      // mounted row must NOT end up with tabIndex=-1.
      const wrapper = container.querySelector('.mac-table-scroll-wrapper') as HTMLElement;
      wrapper.scrollTop = 200 * 20 - 200;
      fireEvent.scroll(wrapper);
      await waitFor(() => {
        expect(screen.getByText('Name 199').closest('tr')).toBeInTheDocument();
      });
      expect(screen.queryByText('Name 0')).toBeNull();

      // Exactly ONE mounted row carries tabIndex=0 — the window keeps a tab
      // stop while the active row is off-window. The stop is the FIRST row
      // of the rendered virtual window (overscan included).
      const mountedRows = Array.from(
        container.querySelectorAll('tbody tr[data-row-index]')
      ) as HTMLElement[];
      expect(mountedRows.length).toBeGreaterThan(0);
      const tabStops = mountedRows.filter((tr) => tr.getAttribute('tabIndex') === '0');
      expect(tabStops.length).toBe(1);
      expect(tabStops[0]).toBe(mountedRows[0]);
    } finally {
      // The DT-13..16 block restores/deletes these descriptors in its own
      // afterEach — they may be absent here, so restore only when defined.
      if (trDescriptor) {
        Object.defineProperty(HTMLTableRowElement.prototype, 'offsetHeight', trDescriptor);
      } else {
        Reflect.deleteProperty(HTMLTableRowElement.prototype, 'offsetHeight');
      }
      if (divDescriptor) {
        Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', divDescriptor);
      } else {
        Reflect.deleteProperty(HTMLDivElement.prototype, 'offsetHeight');
      }
    }
  });

  it('DT-42: filter clearing compares against EFFECTIVE visibility (normalized map) (Codex P2 round 6)', () => {
    const onFilter = vi.fn();
    const onColumnVisibilityChange = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={rows}
        filterable
        filterConfig={{ name: 'Bo' }}
        onFilter={onFilter}
        showColumnToggle
        // All-false map: normalized to all-visible.
        columnVisibility={{ name: false, age: false, city: false }}
        onColumnVisibilityChange={onColumnVisibilityChange}
      />
    );

    // Uncheck 'name' (rendered visible via normalization, filter active).
    fireEvent.click(screen.getByRole('button', { name: /Колонки|Columns/ }));
    fireEvent.click(screen.getByLabelText('Name'));

    // The filter IS cleared: the comparison uses the effective map, not the
    // raw all-false one.
    expect(onFilter).toHaveBeenCalledWith('name', '');
  });

  it('DT-43: normalization preserves visibility entries for ABSENT columns (Codex P2 round 7)', () => {
    const onColumnVisibilityChange = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={rows}
        showColumnToggle
        // All current columns false (normalizes to all-visible) + a stale
        // entry for a temporarily-absent column ('legacy_col').
        columnVisibility={{ name: false, age: false, city: false, legacy_col: false }}
        onColumnVisibilityChange={onColumnVisibilityChange}
      />
    );

    // Current columns render (normalization) and the menu reflects them.
    expect(screen.getByText('Name')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Колонки|Columns/ }));

    // Unchecking a column emits a map that STILL carries the absent column's
    // entry — its persisted state is not silently discarded.
    fireEvent.click(screen.getByLabelText('Name'));
    expect(onColumnVisibilityChange).toHaveBeenCalledWith(
      expect.objectContaining({ legacy_col: false, name: false })
    );
  });

  it('DT-44: focusing a non-active row syncs the roving index (Codex P2 round 7)', async () => {
    render(<DataTable columns={columns} data={rows} keyboardNavigation />);

    // Direct focus on the LAST row (pointer/programmatic focus path).
    const last = getRowByName('Carol');
    last.focus();
    await waitFor(() => expect(getRowByName('Carol')).toHaveAttribute('tabIndex', '0'));
    await waitFor(() => expect(getRowByName('Alice')).toHaveAttribute('tabIndex', '-1'));

    // ArrowDown moves relative to the FOCUSED row — clamped at the last row,
    // NOT jumping from the old active row 0.
    fireEvent.keyDown(last, { key: 'ArrowDown' });
    expect(getRowByName('Carol')).toHaveAttribute('tabIndex', '0');
    expect(getRowByName('Alice')).toHaveAttribute('tabIndex', '-1');

    // ArrowUp from the focused last row goes to row 1 (not row 0→1 semantics
    // of a stale index): the roving index followed the actual focus.
    fireEvent.keyDown(last, { key: 'ArrowUp' });
    expect(getRowByName('Bob')).toHaveAttribute('tabIndex', '0');
  });

});

describe('DataTable — PR-UI-12 toolbar i18n contract (DT-28)', () => {
  it('DT-28: table.* toolbar keys exist and are non-empty in all 5 locales', async () => {
    const locales: Record<string, Record<string, unknown>> = {
      ru: (await import('../../../i18n/locales/ru')).default,
      en: (await import('../../../i18n/locales/en')).default,
      kk: (await import('../../../i18n/locales/kk')).default,
      'uz-Latn': (await import('../../../i18n/locales/uz-Latn')).default,
      'uz-Cyrl': (await import('../../../i18n/locales/uz-Cyrl')).default
    };
    const KEYS = [
      'columns',
      'columns_menu',
      'density',
      'density_compact',
      'density_comfortable',
      'density_spacious'
    ];
    for (const [localeCode, locale] of Object.entries(locales)) {
      const table = (locale as { table?: Record<string, unknown> }).table;
      expect(table, `locale ${localeCode} must define the table.* namespace`).toBeDefined();
      for (const key of KEYS) {
        const value = table?.[key];
        expect(
          typeof value === 'string' && value.trim().length > 0,
          `locale ${localeCode}: table.${key} must be a non-empty string (got ${String(value)})`
        ).toBe(true);
      }
    }
  });
});
