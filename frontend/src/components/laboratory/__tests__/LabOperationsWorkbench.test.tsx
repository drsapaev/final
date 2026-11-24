import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LabOperationsWorkbench from '../LabOperationsWorkbench';

const api = vi.hoisted(() => ({ importRows: vi.fn(), metrics: vi.fn() }));

vi.mock('../../../api/labOperations', () => ({ labOperationsApi: api }));
vi.mock('../../../utils/tokenManager', () => ({ default: { getUserData: () => ({ role: 'Admin' }) } }));

const updatedAt = '2026-11-24T05:00:00+05:00';

function fillManualRow(index: number, report: string) {
  for (const [label, value] of [
    ['Отчёт', report], ['Штрихкод пробы', 'SP-SYNTHETIC'], ['Код показателя', 'LAB-X'], ['Результат', '0'],
  ]) {
    fireEvent.change(screen.getByRole('textbox', { name: `${label} ${index}` }), { target: { value } });
  }
}

describe('Laboratory operations', () => {
  beforeEach(() => vi.resetAllMocks());

  it('preserves the invalid row and applies the valid row at its original position', async () => {
    const onQueueChanged = vi.fn().mockResolvedValue(undefined);
    const invalid = { row_index: 0, message_id: null, report_instance_id: null, status: 'error',
      error_code: 'invalid_row', updated_at: null, existing_values: 0 };
    const valid = { row_index: 1, message_id: 'row-two', report_instance_id: 42, status: 'ready',
      error_code: null, updated_at: updatedAt, existing_values: 0 };
    api.importRows.mockResolvedValueOnce({ rows: [invalid, valid] })
      .mockResolvedValueOnce({ rows: [{ ...valid, row_index: 0, status: 'saved' }] });

    render(<LabOperationsWorkbench orderId={null} reportId={null} onQueueChanged={onQueueChanged} />);
    fillManualRow(1, '11');
    fireEvent.click(screen.getByRole('button', { name: 'Добавить строку' }));
    fillManualRow(2, '42');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить строки' }));

    expect(await screen.findByText('Проверьте поля строки')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить проверенные строки' }));
    expect(await screen.findByText('Сохранено')).toBeInTheDocument();
    expect(api.importRows).toHaveBeenLastCalledWith('manual', [expect.objectContaining({
      report_instance_id: 42, expected_updated_at: updatedAt,
    })], false);
    const rows = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(rows[0]).toHaveTextContent('Строка 1');
    expect(rows[0]).toHaveTextContent('Проверьте поля строки');
    expect(rows[1]).toHaveTextContent('Строка 2');
    expect(rows[1]).toHaveTextContent('Сохранено');
    expect(onQueueChanged).toHaveBeenCalledOnce();
  });

  it('shows the coded rejection counts and includes uncategorized history', async () => {
    api.metrics.mockResolvedValue({ rejected_samples: 3, rejected_samples_by_reason: {
      unknown: 1, insufficient_quantity: 2,
    } });
    render(<LabOperationsWorkbench orderId={null} reportId={null} onQueueChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Показатели' }));

    await screen.findByText('Недостаточный объём');
    const reasons = within(screen.getByLabelText('Причины отклонения проб'));
    expect(reasons.getByText('Недостаточный объём').nextElementSibling).toHaveTextContent('2');
    expect(reasons.getByText('Категория не указана').nextElementSibling).toHaveTextContent('1');
  });
});
