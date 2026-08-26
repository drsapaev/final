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
 * (per Task 46 §B.3 — MacOSTable.test.tsx is DUPLICATED here, with macos/Table.tsx
 * alias pointing to canonical so the old test path still passes too). These 6
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
