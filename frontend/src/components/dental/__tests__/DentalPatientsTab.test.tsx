import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../../test/renderWithProviders';
import type { PatientId } from '../../../types/domain/branded';
import DentalPatientsTab from '../DentalPatientsTab';

const searchPatients = vi.hoisted(() => vi.fn());
vi.mock('../../../api/patients', () => ({ searchPatients }));

describe('DentalPatientsTab server search', () => {
  beforeEach(() => vi.clearAllMocks());

  it('uses the server search and routes one result through the patient selection action', async () => {
    searchPatients.mockResolvedValue([{
      id: '7' as PatientId,
      full_name: 'SYNTHETIC-Patient',
      phone: '+998900000000',
    }]);
    const onSelectPatient = vi.fn();
    renderWithProviders(<DentalPatientsTab onSelectPatient={onSelectPatient} />);

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Sy' } });
    expect(await screen.findByText('SYNTHETIC-Patient')).toBeInTheDocument();
    expect(searchPatients).toHaveBeenCalledWith('Sy');
    fireEvent.click(screen.getByRole('button', { name: /Выбрать пациента|Select patient/ }));
    expect(onSelectPatient).toHaveBeenCalledWith(expect.objectContaining({ patient_id: '7', name: 'SYNTHETIC-Patient' }));
  });

  it('does not query with a one-character term and provides a queue route on no results', async () => {
    searchPatients.mockResolvedValue([]);
    const onGoToQueue = vi.fn();
    renderWithProviders(<DentalPatientsTab onGoToQueue={onGoToQueue} />);

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'S' } });
    expect(searchPatients).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Sy' } });
    expect(await screen.findByText(/No patients found|Пациенты не найдены/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Открыть очередь|Open queue/ }));
    expect(onGoToQueue).toHaveBeenCalledOnce();
  });
});
