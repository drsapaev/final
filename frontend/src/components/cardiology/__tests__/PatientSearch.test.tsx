/**
 * PatientSearch tests — cardioplan slice 4 ("Пациенты и AI").
 *
 * Contract under test:
 *  - no request fires below 2 characters (client-side guard);
 *  - distinct loading / empty / error states (a failed request must never
 *    look like a verified "no patients found");
 *  - picking a result hands the canonical patient up to the panel.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, beforeEach, expect, vi } from 'vitest';

const apiClientGet = vi.fn();

vi.mock('../../../api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => apiClientGet(...args),
  },
}));

vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
    isDark: false,
    getColor: () => '#111827',
    getSpacing: (size: string) => (size === 'sm' ? '4px' : '8px'),
    getFontSize: () => '14px',
  }),
}));

import PatientSearch from '../PatientSearch';

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('PatientSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not query the backend below 2 characters', async () => {
    render(<PatientSearch onPick={vi.fn()} />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'И' } });
    await sleep(450);

    expect(apiClientGet).not.toHaveBeenCalled();
    expect(screen.getByText('Введите минимум 2 символа — ФИО или телефон')).toBeInTheDocument();
  });

  it('searches from 2 characters and renders the results', async () => {
    apiClientGet.mockResolvedValue({
      data: [
        { id: 7, full_name: 'Иванов Иван Иванович', phone: '+7 900 000-00-00', birth_date: '1980-05-01' },
      ],
    });

    render(<PatientSearch onPick={vi.fn()} />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Ив' } });

    await waitFor(() => {
      expect(apiClientGet).toHaveBeenCalledWith('/patients/', { params: { q: 'Ив', limit: 20 } });
    }, { timeout: 2000 });

    await waitFor(() => {
      expect(screen.getByText('Иванов Иван Иванович')).toBeInTheDocument();
    });
    expect(screen.getByText(/1980/)).toBeInTheDocument();
  });

  it('shows a distinct error state and retries on demand', async () => {
    apiClientGet.mockRejectedValueOnce(new Error('network down'));

    render(<PatientSearch onPick={vi.fn()} />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Ив' } });

    await waitFor(() => {
      expect(screen.getByText('Не удалось загрузить пациентов')).toBeInTheDocument();
    }, { timeout: 2000 });
    // An error must not look like a verified empty result.
    expect(screen.queryByText('Пациенты не найдены')).not.toBeInTheDocument();

    apiClientGet.mockResolvedValueOnce({
      data: [{ id: 3, full_name: 'Петров Пётр', phone: '', birth_date: null }],
    });
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));

    await waitFor(() => {
      expect(screen.getByText('Петров Пётр')).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  it('shows the empty state only for a verified empty response', async () => {
    apiClientGet.mockResolvedValue({ data: [] });

    render(<PatientSearch onPick={vi.fn()} />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Ив' } });

    await waitFor(() => {
      expect(screen.getByText('Пациенты не найдены')).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  it('hands the picked patient up to the panel', async () => {
    const onPick = vi.fn();
    apiClientGet.mockResolvedValue({
      data: [{ id: 7, full_name: 'Иванов Иван', phone: '+7 900', birth_date: '1980-05-01' }],
    });

    render(<PatientSearch onPick={onPick} />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Ив' } });
    await waitFor(() => {
      expect(screen.getByText('Иванов Иван')).toBeInTheDocument();
    }, { timeout: 2000 });

    fireEvent.click(screen.getByText('Иванов Иван'));
    expect(onPick).toHaveBeenCalledWith({
      id: 7,
      full_name: 'Иванов Иван',
      phone: '+7 900',
      birth_year: '1980',
    });
  });
});
