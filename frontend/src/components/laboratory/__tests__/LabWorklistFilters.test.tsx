import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import LabWorklistFilters from '../LabWorklistFilters';

const counts = { actionable: 61, today: 39, overdue: 15, awaiting_specimen: 12, in_review: 8, ready: 24 };

describe('Lab v2 worklist controls', () => {
  it('forwards the full search and allows server scope and sort to change', async () => {
    const onChange = vi.fn();
    render(<LabWorklistFilters counts={counts} onChange={onChange} />);

    const search = screen.getByRole('searchbox', { name: /пациент, заказ/i });
    fireEvent.change(search, { target: { value: 'SYNTHETIC-' } });
    fireEvent.change(search, { target: { value: 'SYNTHETIC-61' } });
    expect(screen.getByRole('option', { name: 'Требуют действий (61)' })).toBeInTheDocument();
    await waitFor(() => expect(onChange).toHaveBeenCalledTimes(1));
    expect(onChange).toHaveBeenLastCalledWith({ view: 'actionable', sort: 'oldest', q: 'SYNTHETIC-61' });

    fireEvent.change(screen.getByRole('combobox', { name: 'Рабочая область' }), { target: { value: 'overdue' } });
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ view: 'overdue' })));
  });

  it('uses a separate exact-barcode submission and restores the regular search when cleared', async () => {
    const onChange = vi.fn();
    render(<LabWorklistFilters counts={counts} onChange={onChange} />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'SYNTHETIC-QUEUE' } });
    await waitFor(() => expect(onChange).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: 'Сканировать' }));
    expect(screen.getByRole('textbox', { name: 'Штрихкод пробы' })).toHaveFocus();
    fireEvent.change(screen.getByRole('textbox', { name: 'Штрихкод пробы' }), { target: { value: '  SP-0123456789ABCDEF  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Найти пробу' }));
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith({
      view: 'actionable', sort: 'oldest', q: '', barcode: 'SP-0123456789ABCDEF',
    }));

    fireEvent.click(screen.getByRole('button', { name: /очистить/i }));
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      q: 'SYNTHETIC-QUEUE', barcode: undefined,
    })));
  });
});
