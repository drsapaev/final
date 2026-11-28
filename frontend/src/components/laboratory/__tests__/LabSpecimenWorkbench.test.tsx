import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import type { LabSpecimen } from '../../../types/features/labWorkspace';
import LabSpecimenWorkbench from '../LabSpecimenWorkbench';

const api = vi.hoisted(() => ({ list: vi.fn(), createForVisit: vi.fn(), scan: vi.fn(), addEvent: vi.fn() }));
vi.mock('../../../api/labSpecimens', () => ({ labSpecimensApi: api }));

const specimen: LabSpecimen = {
  id: 701, order_id: 502, visit_id: 91, barcode: 'SP-0123456789ABCDEF',
  material_code: 'blood', container_code: 'tube', status: 'received', revision: 3,
  collected_at: null, received_at: null, accepted_at: null, latest_reason: null,
  parent_specimen_id: null, replaces_specimen_id: null,
  visit_service_ids: [43], report_instance_ids: [], events: [], available_actions: ['hold'],
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })));
});

afterEach(() => vi.unstubAllGlobals());

describe('Lab v2 specimen workbench', () => {
  it('establishes an order against an explicitly selected visit test before a report exists', async () => {
    api.createForVisit.mockResolvedValue(specimen);
    const onOrderEstablished = vi.fn();
    const onPendingChange = vi.fn();
    render(<ThemeProvider><LabSpecimenWorkbench orderId={null} visitId={91} activeReportId={null}
      services={[{ id: 43, label: 'SYNTHETIC-TEST' }]} onChanged={vi.fn()}
      onPendingChange={onPendingChange} onOrderEstablished={onOrderEstablished} /></ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Зарегистрировать пробу' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Код материала' }), { target: { value: 'blood' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'Код контейнера' }), { target: { value: 'tube' } });
    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: 'SYNTHETIC-TEST #43' }));
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(onOrderEstablished).toHaveBeenCalledWith(502, 91));
    expect(api.createForVisit).toHaveBeenCalledWith(91, {
      visit_service_ids: [43], report_instance_ids: [], material_code: 'blood', container_code: 'tube', request_id: expect.any(String),
    });
    expect(api.list).not.toHaveBeenCalled();
    expect(onPendingChange.mock.calls).toEqual([[true], [false]]);
  });

  it('keeps a scanned specimen from a different order out of the current order', async () => {
    api.list.mockResolvedValue({ items: [specimen], data_status: 'known' });
    api.scan.mockResolvedValue({ ...specimen, id: 702, order_id: 503 });
    render(<ThemeProvider><LabSpecimenWorkbench orderId={502} visitId={91} activeReportId={null} services={[]}
      onChanged={vi.fn()} onPendingChange={vi.fn()} onOrderEstablished={vi.fn()} /></ThemeProvider>);
    const barcode = await screen.findByRole('textbox', { name: 'Штрихкод пробы этого заказа' });
    fireEvent.change(barcode, { target: { value: specimen.barcode } });
    fireEvent.click(screen.getByRole('button', { name: 'Найти пробу' }));

    expect(await screen.findByText(/проба не найдена в этом заказе/i)).toBeInTheDocument();
    expect(api.scan).toHaveBeenCalledWith(502, specimen.barcode, expect.any(AbortSignal));
    expect(screen.queryByText(/выбрана проба/)).toBeNull();
  });

  it('submits the selected rejection category separately from its custody note', async () => {
    api.list.mockResolvedValue({ items: [{ ...specimen, available_actions: ['reject'] }], data_status: 'known' });
    api.addEvent.mockResolvedValue({ ...specimen, status: 'rejected', available_actions: [] });
    render(<ThemeProvider><LabSpecimenWorkbench orderId={502} visitId={91} activeReportId={null} services={[]}
      onChanged={vi.fn()} onPendingChange={vi.fn()} onOrderEstablished={vi.fn()} /></ThemeProvider>);

    fireEvent.click(await screen.findByRole('button', { name: 'Отклонить пробу' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Категория отклонения' }), { target: { value: 'label_mismatch' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'Причина' }), { target: { value: 'SYNTHETIC-CUSTODY-NOTE' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(api.addEvent).toHaveBeenCalledWith(701, {
      action: 'reject', expected_revision: 3, reason: 'SYNTHETIC-CUSTODY-NOTE',
      reason_code: 'label_mismatch', request_id: expect.any(String),
    }));
  });
});
