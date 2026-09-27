import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes } from 'react';
import type { Patient } from '../../../types/domain/clinic';
import DermaPatientsTab, { type DermatologyPatientRecord } from '../DermaPatientsTab';

const { searchPatientsMock } = vi.hoisted(() => ({ searchPatientsMock: vi.fn() }));

vi.mock('../../../api/patients', () => ({ searchPatients: searchPatientsMock }));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string, options?: Record<string, unknown>) =>
    options ? `${key}:${String(options.count ?? options.id ?? '')}` : key }),
}));
vi.mock('../../../components/ui/macos', async () => {
  const React = await import('react');
  return {
    Badge: ({ children, ...props }: HTMLAttributes<HTMLSpanElement>) =>
      React.createElement('span', props, children),
    Button: ({ children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) =>
      React.createElement('button', props, children),
    Card: ({ children, ...props }: HTMLAttributes<HTMLDivElement>) =>
      React.createElement('section', props, children),
    Input: ({ icon: _icon, ...props }: InputHTMLAttributes<HTMLInputElement> & { icon?: unknown }) =>
      React.createElement('input', props),
  };
});

const emptyProps = {
  selectedPatient: null,
  onSelectPatient: vi.fn(),
  appointments: [],
  skinExaminations: [],
  cosmeticProcedures: [],
  historyLoading: false,
  historyReady: false,
  historyError: false,
};

describe('DermaPatientsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('waits for two characters before searching through the patient API helper', async () => {
    searchPatientsMock.mockResolvedValue([]);
    render(<DermaPatientsTab {...emptyProps} />);
    const search = screen.getByRole('searchbox', { name: 'derma.derma_panel_patients_search_label' });

    fireEvent.change(search, { target: { value: 'A' } });
    await new Promise((resolve) => window.setTimeout(resolve, 350));
    expect(searchPatientsMock).not.toHaveBeenCalled();

    fireEvent.change(search, { target: { value: 'AB' } });
    await waitFor(() => expect(searchPatientsMock).toHaveBeenCalledWith('AB'));
  });

  it('shows a provided birth year as a year and only offers patient history after selection', async () => {
    searchPatientsMock.mockResolvedValue([]);
    const selectedPatient: DermatologyPatientRecord = {
      id: 42,
      patient_id: 42,
      patient_name: 'SYNTHETIC-Patient-42',
      patient_birth_year: 1985,
    };
    const props = { ...emptyProps, selectedPatient, historyReady: true };
    const { rerender } = render(<DermaPatientsTab {...emptyProps} />);

    expect(screen.getByText('derma.derma_panel_patient_history_select_prompt')).toBeInTheDocument();
    expect(screen.queryByText('derma.derma_panel_patient_history_title')).not.toBeInTheDocument();

    rerender(<DermaPatientsTab {...props} />);
    expect(screen.getByText('1985')).toBeInTheDocument();
    expect(screen.queryByText('1985-01-01')).not.toBeInTheDocument();
    expect(screen.getByText('derma.derma_panel_patient_history_title')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'derma.derma_panel_patients_clear_selection' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'derma.derma_panel_button_exam' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'derma.derma_panel_button_procedure' })).not.toBeInTheDocument();
  });

  it('selects the patient returned by search without exposing an aggregate list', async () => {
    const patient = {
      id: 77,
      first_name: 'SYNTHETIC-First',
      last_name: 'SYNTHETIC-Last',
      middle_name: null,
      full_name: 'SYNTHETIC-Patient-77',
      phone: null,
      birth_date: null,
      created_at: '2026-01-01T00:00:00Z',
    } as unknown as Patient;
    searchPatientsMock.mockResolvedValue([patient]);
    const onSelectPatient = vi.fn();
    render(<DermaPatientsTab {...emptyProps} onSelectPatient={onSelectPatient} />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'SY' } });

    const selectButton = await screen.findByRole('button', { name: 'derma.derma_panel_patients_select' });
    fireEvent.click(selectButton);

    expect(onSelectPatient).toHaveBeenCalledWith(expect.objectContaining({
      id: 77,
      patient_id: 77,
      patient_name: 'SYNTHETIC-Patient-77',
    }));
  });
});
