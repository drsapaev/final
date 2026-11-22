import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';

const { apiGet, apiPost } = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
vi.mock('../api/client', () => ({ api: { get: apiGet, post: apiPost } }));

import PatientBookingPanel from '../components/patient/PatientBookingPanel';

describe('PatientBookingPanel exact service selection', () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiGet.mockResolvedValue({ data: [{ id: 81, name: 'Консультация терапевта' }] });
    apiPost.mockReset();
    apiPost.mockImplementation((url: string, body: Record<string, unknown>) => {
      if (url.endsWith('/booking/services')) {
        return Promise.resolve({ data: { service_ids: [81] } });
      }
      if (url.endsWith('/booking/departments')) {
        return Promise.resolve({ data: { departments: [] } });
      }
      if (url.endsWith('/appointments/preview')) {
        return Promise.resolve({ data: { preview_only: true, appointment: body } });
      }
      if (url.endsWith('/appointments')) {
        return Promise.resolve({
          data: { appointment_id: 17, preview: { appointment: body } },
        });
      }
      return Promise.resolve({ data: {} });
    });
    (window as unknown as { Telegram?: unknown }).Telegram = {
      WebApp: { initData: 'test-init-data-payload' },
    };
  });

  afterEach(() => {
    delete (window as unknown as { Telegram?: unknown }).Telegram;
  });

  it('sends the catalog service ID for preview and booking', async () => {
    render(
      <ThemeProvider>
        <PatientBookingPanel />
      </ThemeProvider>,
    );

    const serviceSelector = await screen.findByLabelText('Услуги');
    fireEvent.click(serviceSelector);
    fireEvent.click(await screen.findByRole('option', { name: 'Консультация терапевта' }));

    fireEvent.click(screen.getByRole('button', { name: 'Проверить заявку' }));
    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        '/telegram/mini-app/appointments/preview',
        expect.objectContaining({ serviceIds: [81], services: ['Консультация терапевта'] }),
      );
    });

    fireEvent.click(screen.getByRole('button', { name: 'Записаться' }));
    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        '/telegram/mini-app/appointments',
        expect.objectContaining({ serviceIds: [81], services: ['Консультация терапевта'] }),
      );
    });
  });

  it('filters service choices to the selected department', async () => {
    apiGet.mockResolvedValue({
      data: [
        { id: 81, name: 'Кардиология', department_key: 'cardiology' },
        { id: 82, name: 'Дерматология', department_key: 'dermatology' },
        { id: 83, name: 'Общая услуга', department_key: null },
      ],
    });
    apiPost.mockImplementation((url: string) => {
      if (url.endsWith('/booking/services')) {
        return Promise.resolve({ data: { service_ids: [81, 82, 83] } });
      }
      if (url.endsWith('/booking/departments')) {
        return Promise.resolve({
          data: { departments: [{ key: 'cardio', name: 'Кардиология' }, { key: 'derma', name: 'Дерматология' }] },
        });
      }
      return Promise.resolve({ data: {} });
    });
    render(
      <ThemeProvider>
        <PatientBookingPanel />
      </ThemeProvider>,
    );

    fireEvent.click(await screen.findByLabelText('Отделение'));
    fireEvent.click(await screen.findByRole('option', { name: 'Кардиология' }));
    fireEvent.click(await screen.findByLabelText('Услуги'));

    expect(await screen.findByRole('option', { name: 'Кардиология' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Общая услуга' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Дерматология' })).not.toBeInTheDocument();
  });

  it('shows only services approved in the online-booking settings', async () => {
    apiGet.mockResolvedValue({
      data: [
        { id: 81, name: 'Разрешённая услуга' },
        { id: 82, name: 'Не разрешённая услуга' },
      ],
    });
    render(
      <ThemeProvider>
        <PatientBookingPanel />
      </ThemeProvider>,
    );

    fireEvent.click(await screen.findByLabelText('Услуги'));

    expect(await screen.findByRole('option', { name: 'Разрешённая услуга' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Не разрешённая услуга' })).not.toBeInTheDocument();
  });
});
