import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Appointments from '../Appointments';
import Search from '../Search';
import { ThemeProvider } from '../../contexts/ThemeContext';

const mocks = vi.hoisted(() => ({
  appointments: vi.fn(),
  visit: vi.fn(),
  patient: vi.fn(),
  patients: vi.fn(),
  visitList: vi.fn(),
}));

vi.mock('../../api/client', () => ({ api: { get: mocks.appointments } }));
vi.mock('../../api', () => ({ api: { get: mocks.visitList } }));
vi.mock('../../api/visits', () => ({ getVisit: mocks.visit }));
vi.mock('../../api/patients', () => ({ getPatient: mocks.patient, searchPatients: mocks.patients }));
vi.mock('../../components/RoleGate', () => ({ default: ({ children }: { children: React.ReactNode }) => children }));
vi.mock('../../components/AppointmentFlow', () => ({ default: () => null }));
vi.mock('../../components/tables/EnhancedAppointmentsTable', () => ({ default: () => null }));
vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => {
    if (key === 'misc.ue_field_created_at') return 'Дата создания';
    if (key === 'misc.srch_label_search') return 'Поиск';
    return key;
  } }),
}));

describe('clinical calendar dates', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    localStorage.setItem('language', 'ru');
    mocks.patients.mockResolvedValue([]);
    mocks.patient.mockResolvedValue({ id: 1, first_name: 'SYNTHETIC-PATIENT' });
    mocks.visitList.mockResolvedValue({ data: [] });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('filters the scheduled day server-side and accepts the native array without an unfiltered fallback', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-03-05T20:00:00Z')); // March 6 in Tashkent
    mocks.appointments.mockResolvedValue({ data: [] });
    render(<ThemeProvider><Appointments /></ThemeProvider>);
    const day = screen.getByLabelText(/Дата:/);
    expect(day).toHaveValue('2026-03-06');
    await waitFor(() => expect(mocks.appointments).toHaveBeenCalledTimes(1));

    mocks.appointments.mockResolvedValueOnce({ data: [{ id: 123, patient_name: 'SYNTHETIC-SCHEDULED' }] });
    fireEvent.change(day, { target: { value: '2026-03-08' } });
    expect(await screen.findByText('SYNTHETIC-SCHEDULED')).toBeInTheDocument();
    expect(mocks.appointments).toHaveBeenCalledTimes(2);
    expect(mocks.appointments).toHaveBeenLastCalledWith('/appointments', {
      params: { date_from: '2026-03-08', date_to: '2026-03-08', limit: 200 },
    });

    fireEvent.change(day, { target: { value: '' } });
    await waitFor(() => expect(screen.queryByText('SYNTHETIC-SCHEDULED')).not.toBeInTheDocument());
    expect(mocks.appointments).toHaveBeenCalledTimes(2);
  });

  it('clears the old day immediately and ignores a slow response when switching again', async () => {
    mocks.appointments.mockResolvedValueOnce({ data: [{ id: 1, patient_name: 'SYNTHETIC-OLD' }] });
    let finishSlowDay!: (value: { data: { id: number; patient_name: string }[] }) => void;
    mocks.appointments.mockImplementationOnce(() => new Promise(resolve => { finishSlowDay = resolve; }));
    mocks.appointments.mockResolvedValueOnce({ data: [{ id: 3, patient_name: 'SYNTHETIC-LATEST' }] });
    render(<ThemeProvider><Appointments /></ThemeProvider>);
    expect(await screen.findByText('SYNTHETIC-OLD')).toBeInTheDocument();
    const day = screen.getByLabelText(/Дата:/);
    fireEvent.change(day, { target: { value: '2026-03-08' } });
    expect(screen.queryByText('SYNTHETIC-OLD')).not.toBeInTheDocument();
    expect(screen.queryByText('misc.appo_net_zapisey_na_vybrannuyu_da')).not.toBeInTheDocument();
    fireEvent.change(day, { target: { value: '2026-03-09' } });
    expect(await screen.findByText('SYNTHETIC-LATEST')).toBeInTheDocument();
    await act(async () => finishSlowDay({ data: [{ id: 2, patient_name: 'SYNTHETIC-STALE' }] }));
    expect(screen.queryByText('SYNTHETIC-STALE')).not.toBeInTheDocument();
    expect(screen.getByText('SYNTHETIC-LATEST')).toBeInTheDocument();
  });

  it.each([
    ['2026-03-08', '📅 08.03.2026'],
    [null, '📅 Дата создания: 06.03.2026'],
  ])('distinguishes the scheduled day %s from the creation timestamp', async (plannedDate, expected) => {
    mocks.visit.mockResolvedValue({
      visit: { id: 123, patient_id: 1, planned_date: plannedDate, created_at: '2026-03-05T20:00:00Z' },
    });
    render(<MemoryRouter><Search /></MemoryRouter>);
    const search = screen.getByRole('textbox', { name: 'Поиск' });
    fireEvent.change(search, { target: { value: '123' } });
    fireEvent.submit(search.closest('form')!);
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });
});
