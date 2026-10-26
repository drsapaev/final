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
});
