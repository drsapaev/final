import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { LabImportEntry, LabImportOutcome } from '../../../api/labOperations';
import LabOperationsWorkbench from '../LabOperationsWorkbench';
import { LAB_IMPORT_CSV_HEADER } from '../utils/labImportCsv';

const api = vi.hoisted(() => ({ importRows: vi.fn(), metrics: vi.fn() }));

vi.mock('../../../api/labOperations', () => ({ labOperationsApi: api }));
vi.mock('../../../utils/tokenManager', () => ({ default: { getUserData: () => ({ role: 'Admin' }) } }));

const updatedAt = '2026-11-24T05:00:00+05:00';

function fillManualRow(index: number, report: string, analyte = 'LAB-X') {
  for (const [label, value] of [
    ['Отчёт', report], ['Штрихкод пробы', 'SP-SYNTHETIC'], ['Код показателя', analyte], ['Результат', '0'],
  ]) {
    fireEvent.change(screen.getByRole('textbox', { name: `${label} ${index}` }), { target: { value } });
  }
}

function importOutcomes(entries: LabImportEntry[], status: LabImportOutcome['status']): LabImportOutcome[] {
  return entries.map((entry, index) => ({
    row_index: index,
    message_id: entry.message_id,
    report_instance_id: entry.report_instance_id,
    status,
    updated_at: updatedAt,
    existing_values: 0,
    error_code: null,
  }));
}

describe('Laboratory operations', () => {
  beforeEach(() => vi.resetAllMocks());

  it('previews a malformed CSV message and saves the flagged sibling in place', async () => {
    const invalid = { row_index: 0, message_id: null, report_instance_id: null, status: 'error',
      error_code: 'invalid_row', updated_at: null, existing_values: 0 };
    const messageId = '00000000-0000-4000-8000-000000000002';
    const valid = { row_index: 1, message_id: messageId, report_instance_id: 42, status: 'ready',
      error_code: null, updated_at: updatedAt, existing_values: 0 };
    api.importRows.mockResolvedValueOnce({ rows: [invalid, valid] })
      .mockResolvedValueOnce({ rows: [{ ...valid, row_index: 0, status: 'saved' }] });
    const file = new File([], 'synthetic.csv', { type: 'text/csv' });
    Object.defineProperty(file, 'text', { value: async () => [
      LAB_IMPORT_CSV_HEADER,
      '00000000-0000-4000-8000-000000000001,0x2a,SP-SYNTHETIC,hgb,g_l,1,,,',
      `${messageId},42,SP-SYNTHETIC,hgb,g_l,7,,,"[""H?""]"`,
    ].join('\n') });

    render(<LabOperationsWorkbench orderId={null} reportId={null} onQueueChanged={vi.fn().mockResolvedValue(undefined)} />);
    fireEvent.click(screen.getByRole('button', { name: 'Импорт CSV' }));
    fireEvent.change(screen.getByLabelText('Импорт CSV'), { target: { files: [file] } });
    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Проверить строки' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Проверить строки' }));
    expect(await screen.findByText('Проверьте поля строки')).toBeInTheDocument();
    expect(api.importRows).toHaveBeenNthCalledWith(1, 'csv', [
      expect.objectContaining({ report_instance_id: 0, values: [] }),
      expect.objectContaining({ report_instance_id: 42, values: [expect.objectContaining({ instrument_flags: ['H?'] })] }),
    ], true);

    fireEvent.click(screen.getByRole('button', { name: 'Сохранить проверенные строки' }));
    expect(await screen.findByText('Сохранено')).toBeInTheDocument();
    expect(api.importRows).toHaveBeenLastCalledWith('csv', [expect.objectContaining({
      message_id: messageId, report_instance_id: 42, expected_updated_at: updatedAt,
      values: [expect.objectContaining({ instrument_flags: ['H?'] })],
    })], false);
    const rows = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(rows[0]).toHaveTextContent('Проверьте поля строки');
    expect(rows[1]).toHaveTextContent('Сохранено');
  });

  it('shows an unmapped analyzer code without making that row saveable', async () => {
    const messageId = '00000000-0000-4000-8000-000000000021';
    api.importRows.mockResolvedValueOnce({ rows: [{
      row_index: 0,
      message_id: messageId,
      report_instance_id: 42,
      status: 'error',
      error_code: 'unknown_analyte',
      unmapped_analyte_code: 'DEVICE-HGB-RAW',
      updated_at: null,
      existing_values: 0,
    }] });
    const file = new File([], 'unmapped.csv', { type: 'text/csv' });
    Object.defineProperty(file, 'text', { value: async () => [
      LAB_IMPORT_CSV_HEADER,
      `${messageId},42,SP-SYNTHETIC,DEVICE-HGB-RAW,g_l,11,,,`,
    ].join('\n') });

    render(<LabOperationsWorkbench orderId={null} reportId={null} onQueueChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Импорт CSV' }));
    fireEvent.change(screen.getByLabelText('Импорт CSV'), { target: { files: [file] } });
    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Проверить строки' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Проверить строки' }));

    expect(await screen.findByText('DEVICE-HGB-RAW')).toBeInTheDocument();
    expect(screen.getByText('Сверьте код с утверждённым сопоставлением анализаторов вашей клиники, исправьте CSV и загрузите его повторно. Строка не сохранена.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Сохранить проверенные строки' })).toBeDisabled();
    expect(api.importRows).toHaveBeenCalledTimes(1);
  });

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

  it('gives a saved group a new import message when an analyte result is edited', async () => {
    const receipts = new Map<string, string>();
    api.importRows.mockImplementation(async (_source, entries: LabImportEntry[], preview: boolean) => ({
      rows: importOutcomes(entries, preview ? 'ready' : 'saved').map((outcome, index) => {
        const entry = entries[index];
        const content = JSON.stringify(entry.values);
        const recorded = receipts.get(entry.message_id);
        if (recorded !== undefined) {
          return recorded === content
            ? { ...outcome, status: 'duplicate' }
            : { ...outcome, status: 'error', error_code: 'message_conflict' };
        }
        if (!preview) receipts.set(entry.message_id, content);
        return { ...outcome, existing_values: preview && receipts.size ? entry.values.length : 0 };
      }),
    }));
    render(<LabOperationsWorkbench orderId={null} reportId={42} onQueueChanged={vi.fn().mockResolvedValue(undefined)} />);
    fillManualRow(1, '42');
    fireEvent.click(screen.getByRole('button', { name: 'Добавить строку' }));
    fillManualRow(2, '42', 'LAB-Y');
    const preview = screen.getByRole('button', { name: 'Проверить строки' });
    const save = screen.getByRole('button', { name: 'Сохранить проверенные строки' });

    fireEvent.click(preview);
    await screen.findByText('Готово к сохранению');
    fireEvent.click(save);
    await screen.findByText('Сохранено');
    const [original] = api.importRows.mock.calls[1][1] as LabImportEntry[];
    expect(original.values).toHaveLength(2);

    fireEvent.change(screen.getByRole('textbox', { name: 'Результат 2' }), { target: { value: '5' } });
    fireEvent.click(preview);
    await screen.findByText('Готово к сохранению');
    const [edited] = api.importRows.mock.calls[2][1] as LabImportEntry[];
    expect(edited.message_id).not.toBe(original.message_id);
    expect(edited.values).toEqual([
      { analyte_code: 'LAB-X', unit_code: null, value_text: '0' },
      { analyte_code: 'LAB-Y', unit_code: null, value_text: '5' },
    ]);
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Разрешить замену показанных сохранённых значений' }));
    fireEvent.click(save);
    await screen.findByText('Сохранено');
    expect(api.importRows).toHaveBeenLastCalledWith('manual', [{
      ...edited, expected_updated_at: updatedAt, replace_existing: true,
    }], false);
  });

  it('reuses the exact grouped message across a lost response and another preview', async () => {
    api.importRows
      .mockImplementationOnce(async (_source, entries: LabImportEntry[]) => ({ rows: importOutcomes(entries, 'ready') }))
      .mockRejectedValueOnce(new Error('response lost'))
      .mockImplementation(async (_source, entries: LabImportEntry[]) => ({ rows: importOutcomes(entries, 'duplicate') }));
    render(<LabOperationsWorkbench orderId={null} reportId={42} onQueueChanged={vi.fn()} />);
    fillManualRow(1, '42');
    fireEvent.click(screen.getByRole('button', { name: 'Добавить строку' }));
    fillManualRow(2, '42', 'LAB-Y');
    const preview = screen.getByRole('button', { name: 'Проверить строки' });
    const save = screen.getByRole('button', { name: 'Сохранить проверенные строки' });

    fireEvent.click(preview);
    await screen.findByText('Готово к сохранению');
    fireEvent.click(save);
    await screen.findByRole('alert');
    const initialSubmission = api.importRows.mock.calls[1];

    fireEvent.click(save);
    await screen.findByText('Уже импортировано');
    expect(api.importRows.mock.calls[2]).toEqual(initialSubmission);

    fireEvent.click(preview);
    await screen.findByText('Уже импортировано');
    expect(api.importRows.mock.calls[3]).toEqual(api.importRows.mock.calls[0]);
    expect(save).toBeDisabled();
  });

  it.each([['Отчёт', '43'], ['Штрихкод пробы', 'SP-OTHER']])(
    'changes the message IDs of both affected groups after moving %s',
    async (label, target) => {
      api.importRows.mockImplementation(async (_source, entries: LabImportEntry[]) => ({
        rows: importOutcomes(entries, 'ready'),
      }));
      render(<LabOperationsWorkbench orderId={null} reportId={42} onQueueChanged={vi.fn()} />);
      fillManualRow(1, '42');
      const add = screen.getByRole('button', { name: 'Добавить строку' });
      fireEvent.click(add);
      fillManualRow(2, '42', 'LAB-Y');
      fireEvent.click(add);
      fillManualRow(3, '99');
      const preview = screen.getByRole('button', { name: 'Проверить строки' });
      fireEvent.click(preview);
      expect(await screen.findAllByText('Готово к сохранению')).toHaveLength(2);
      const [original, unchanged] = api.importRows.mock.calls[0][1] as LabImportEntry[];

      fireEvent.change(screen.getByRole('textbox', { name: `${label} 2` }), { target: { value: target } });
      fireEvent.click(preview);
      expect(await screen.findAllByText('Готово к сохранению')).toHaveLength(3);
      const [reduced, moved, unaffected] = api.importRows.mock.calls[1][1] as LabImportEntry[];
      expect(reduced.values).toEqual(original.values.slice(0, 1));
      expect(moved.values).toEqual(original.values.slice(1));
      expect(new Set([original.message_id, reduced.message_id, moved.message_id]).size).toBe(3);
      expect(unaffected).toEqual(unchanged);
    },
  );

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
