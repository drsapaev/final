// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import Table from '../Table';

describe('Table Accessibility', () => {
  const columns = [
    { key: 'name', title: 'Name', sortable: true },
    { key: 'age', title: 'Age', sortable: false }
  ];
  const data = [
    { name: 'John', age: 30 },
    { name: 'Jane', age: 25 }
  ];

  it('adds tabIndex and aria-sort to sortable headers', () => {
    render(<Table columns={columns} data={data} />);

    const nameHeader = screen.getByText('Name').closest('th');
    const ageHeader = screen.getByText('Age').closest('th');

    expect(nameHeader).toHaveAttribute('tabIndex', '0');
    expect(nameHeader).toHaveAttribute('aria-sort', 'none');

    expect(ageHeader).not.toHaveAttribute('tabIndex');
    expect(ageHeader).not.toHaveAttribute('aria-sort');
  });

  it('updates aria-sort when column is sorted', () => {
    render(<Table columns={columns} data={data} />);

    const nameHeader = screen.getByText('Name').closest('th');

    fireEvent.click(nameHeader);
    expect(nameHeader).toHaveAttribute('aria-sort', 'ascending');

    fireEvent.click(nameHeader);
    expect(nameHeader).toHaveAttribute('aria-sort', 'descending');
  });

  it('triggers sort on Enter and Space keys', () => {
    const onSort = vi.fn();
    render(<Table columns={columns} data={data} onSort={onSort} />);

    const nameHeader = screen.getByText('Name').closest('th');

    fireEvent.keyDown(nameHeader, { key: 'Enter' });
    expect(onSort).toHaveBeenCalledWith('name', 'asc');

    fireEvent.keyDown(nameHeader, { key: ' ' });
    expect(onSort).toHaveBeenCalledWith('name', 'desc');
  });

  it('adds role="status" and aria-live="polite" to loading state', () => {
    render(<Table columns={columns} loading={true} />);

    const loadingStatus = screen.getByRole('status');
    expect(loadingStatus).toHaveAttribute('aria-live', 'polite');
    expect(loadingStatus).toHaveTextContent(/Загрузка|Loading/i);
  });

  it('adds role="status" and aria-live="polite" to empty state', () => {
    render(<Table columns={columns} data={[]} />);

    const emptyStatus = screen.getByRole('status');
    expect(emptyStatus).toHaveAttribute('aria-live', 'polite');
    expect(emptyStatus).toHaveTextContent(/Нет данных|No data/i);
  });

  it('wraps custom empty state content without nested table rows', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <Table
        columns={columns}
        data={[]}
        emptyState={<div data-testid="empty-state-content">No rows yet</div>}
      />
    );

    const emptyContent = screen.getByTestId('empty-state-content');
    expect(emptyContent.closest('td')).toBe(screen.getByRole('status'));
    expect(emptyContent.closest('tr')).toBe(screen.getByRole('status').closest('tr'));

    const nestingWarnings = consoleError.mock.calls.filter((call) =>
      call.join(' ').includes('validateDOMNesting')
    );
    expect(nestingWarnings).toEqual([]);

    consoleError.mockRestore();
  });
});
