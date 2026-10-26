import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));
vi.mock('../../../api/client', () => ({ api: { get: apiGet } }));

import AppointmentModal from '../AppointmentModal';

describe('AppointmentModal exact service selection', () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiGet.mockResolvedValue({ data: [{ id: 91, name: 'Первичный приём' }] });
  });

  it('includes the selected catalog service ID in the save callback', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const { container } = render(
      <ThemeProvider>
        <AppointmentModal
          isOpen
          onClose={vi.fn()}
          onSave={onSave}
          patients={[{ id: 4, full_name: 'Тестовый пациент' }]}
          doctors={[{ id: 6, user: { full_name: 'Тестовый врач' }, specialty: 'Терапия' }]}
        />
      </ThemeProvider>,
    );

    const serviceSelector = await screen.findByLabelText(/services|услуги/i);
    fireEvent.click(serviceSelector);
    fireEvent.click(await screen.findByRole('option', { name: 'Первичный приём' }));

    fireEvent.click(screen.getByRole('button', { name: 'Выберите пациента' }));
    fireEvent.click(await screen.findByRole('option', { name: 'Тестовый пациент' }));
    fireEvent.click(screen.getByRole('button', { name: 'Выберите врача' }));
    fireEvent.click(await screen.findByRole('option', { name: /Тестовый врач/ }));

    const dateInput = container.querySelector('input[type="date"]');
    const timeInput = container.querySelector('input[type="time"]');
    const reasonInput = container.querySelector('textarea');
    expect(dateInput).not.toBeNull();
    expect(timeInput).not.toBeNull();
    expect(reasonInput).not.toBeNull();
    fireEvent.change(dateInput!, { target: { value: '2026-11-02' } });
    fireEvent.change(timeInput!, { target: { value: '10:00' } });
    fireEvent.change(reasonInput!, { target: { value: 'Плановый приём' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create appointment' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ serviceId: '91' }),
      );
    });
  });
});
