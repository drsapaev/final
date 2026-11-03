import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { getDateOffset } from '@/utils/dateUtils';

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
    // Date-rollover guard: validateForm() rejects PAST dates, so a pinned
    // calendar day turns this suite into a deterministic time bomb the day
    // after (main CI went red on 2026-11-03 over the hardcoded 2026-11-02).
    // A Tashkent-aware dynamic day keeps the fixture future-dated forever.
    fireEvent.change(dateInput!, { target: { value: getDateOffset(7) } });
    fireEvent.change(timeInput!, { target: { value: '10:00' } });
    fireEvent.change(reasonInput!, { target: { value: 'Плановый приём' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create appointment' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ serviceId: '91' }),
      );
    });
  });

  it('filters pinned services to the selected doctor before saving', async () => {
    apiGet.mockResolvedValue({
      data: [
        { id: 91, name: 'Услуга другого врача', doctor_id: 7 },
        { id: 92, name: 'Услуга выбранного врача', doctor_id: 6 },
        { id: 93, name: 'Общая услуга', doctor_id: null },
      ],
    });
    render(
      <ThemeProvider>
        <AppointmentModal
          isOpen
          onClose={vi.fn()}
          onSave={vi.fn()}
          patients={[{ id: 4, full_name: 'Тестовый пациент' }]}
          doctors={[{ id: 6, user: { full_name: 'Тестовый врач' }, specialty: 'Терапия' }]}
        />
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Выберите врача' }));
    fireEvent.click(await screen.findByRole('option', { name: /Тестовый врач/ }));
    fireEvent.click(await screen.findByLabelText(/services|услуги/i));

    expect(await screen.findByRole('option', { name: 'Услуга выбранного врача' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Общая услуга' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Услуга другого врача' })).not.toBeInTheDocument();
  });
});
