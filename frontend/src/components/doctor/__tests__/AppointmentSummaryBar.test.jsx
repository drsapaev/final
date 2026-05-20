import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AppointmentSummaryBar from '../AppointmentSummaryBar';

const summaryItems = [
  { key: 'total', label: 'Всего', value: 3, variant: 'info' },
  { key: 'waiting', label: 'Ожидают', value: 1, variant: 'warning' }
];

describe('AppointmentSummaryBar', () => {
  it('renders summary items as an accessible list and calls refresh', () => {
    const onRefresh = vi.fn();

    render(
      <AppointmentSummaryBar
        ariaLabel="Сводка записей"
        items={summaryItems}
        onRefresh={onRefresh}
      />
    );

    expect(screen.getByRole('list', { name: 'Сводка записей' })).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByLabelText('Всего: 3')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Обновить/i }));

    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('keeps the refresh action disabled while loading', () => {
    const onRefresh = vi.fn();

    render(
      <AppointmentSummaryBar
        ariaLabel="Сводка записей"
        items={summaryItems}
        onRefresh={onRefresh}
        refreshDisabled
      />
    );

    const refreshButton = screen.getByRole('button', { name: /Обновить/i });

    expect(refreshButton).toBeDisabled();
    fireEvent.click(refreshButton);
    expect(onRefresh).not.toHaveBeenCalled();
  });
});
