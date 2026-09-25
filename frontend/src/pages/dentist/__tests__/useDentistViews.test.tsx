/**
 * PR-UI-15-6 unit contract: dentist views + URL deep-link hook smoke
 * (verbatim extraction from DentistPanelUnified — registrar/cashier/doctor
 * decomposition precedent).
 */
import { renderHook, waitFor } from '@testing-library/react';
import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '../../../test/renderWithProviders';
import DentistVisitsView from '../views/DentistVisitsView';
import { dentalCardKeyDown } from '../dentistCardA11y';
import { useDentistUrlPatient } from '../useDentistUrlPatient';
import type { SelectedPatient } from '../dentistContracts';

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

vi.mock('../../../components/dental/DentalVisitScreen', () => ({
  default: ({ patient }: { patient: Record<string, unknown> }) => (
    <div data-testid="visit-screen">{String(patient.patient_name)}</div>
  ),
}));

describe('dentist views (PR-UI-15-6)', () => {
  it('DentistVisitsView directs an empty visit tab to the single patient search', () => {
    const onGoToPatients = vi.fn();
    const onBackToQueue = vi.fn();
    renderWithProviders(
      <DentistVisitsView
        selectedPatient={null}
        loading={false}
        onCompleteVisit={vi.fn()}
        onGoToPatients={onGoToPatients}
        onBackToQueue={onBackToQueue}
        tI18n={t}
      />,
    );
    expect(screen.getByText('dental.dental_panel_visits_title')).toBeInTheDocument();
    screen.getByRole('button', { name: 'dental.dental_dpt_title' }).click();
    expect(onGoToPatients).toHaveBeenCalledOnce();
    expect(screen.queryByTestId('visit-screen')).not.toBeInTheDocument();
  });

  it('DentistVisitsView renders DentalVisitScreen for a selected patient', () => {
    renderWithProviders(
      <DentistVisitsView
        selectedPatient={{ patient_name: 'SYNTHETIC-Selected' } as SelectedPatient}
        loading={false}
        onCompleteVisit={vi.fn()}
        onBackToQueue={vi.fn()}
        onGoToPatients={vi.fn()}
        tI18n={t}
      />,
    );
    expect(screen.getByTestId('visit-screen')).toHaveTextContent('SYNTHETIC-Selected');
  });

  it('dentalCardKeyDown activates on Enter/Space and swallows the event', () => {
    const action = vi.fn();
    const enter = { key: 'Enter', preventDefault: vi.fn() } as unknown as React.KeyboardEvent<HTMLElement>;
    dentalCardKeyDown(enter, action);
    expect(action).toHaveBeenCalledTimes(1);
    expect(enter.preventDefault).toHaveBeenCalled();

    const space = { key: ' ', preventDefault: vi.fn() } as unknown as React.KeyboardEvent<HTMLElement>;
    dentalCardKeyDown(space, action);
    expect(action).toHaveBeenCalledTimes(2);

    const other = { key: 'a', preventDefault: vi.fn() } as unknown as React.KeyboardEvent<HTMLElement>;
    dentalCardKeyDown(other, action);
    expect(action).toHaveBeenCalledTimes(2);
    expect(other.preventDefault).not.toHaveBeenCalled();
  });
});

describe('useDentistUrlPatient (PR-UI-15-6)', () => {
  const makeDeps = (overrides: Record<string, unknown> = {}) => ({
    locationSearch: '',
    patientIdFromUrl: null,
    visitIdFromUrl: null,
    selectedPatient: null,
    appointmentsTableData: [],
    loadDentistryAppointments: vi.fn(async () => []),
    setSelectedPatient: vi.fn(),
    handleTabChange: vi.fn(),
    tI18n: t,
    ...overrides,
  });

  it('does nothing without URL params', async () => {
    const deps = makeDeps();
    renderHook(() => useDentistUrlPatient(deps as never));
    await waitFor(() => expect(deps.setSelectedPatient).not.toHaveBeenCalled());
  });

  it('does nothing when the patient is already loaded for the deep link', async () => {
    const deps = makeDeps({
      patientIdFromUrl: 7,
      selectedPatient: { patient_id: 7, visit_id: 3 } as SelectedPatient,
    });
    renderHook(() => useDentistUrlPatient(deps as never));
    await waitFor(() => expect(deps.setSelectedPatient).not.toHaveBeenCalled());
  });

  it('falls back to a safe URL-fallback patient when the link matches no appointment', async () => {
    const deps = makeDeps({ patientIdFromUrl: 7 });
    renderHook(() => useDentistUrlPatient(deps as never));
    await waitFor(() => expect(deps.setSelectedPatient).toHaveBeenCalledTimes(1));
    const patient = deps.setSelectedPatient.mock.calls[0][0] as SelectedPatient;
    expect(patient.source).toBe('url');
    expect(patient.patient_name).toBe('dental.dental_panel_patient_url_fallback:{"id":7}');
    expect(deps.handleTabChange).toHaveBeenCalledWith('patients');
  });

  it('selects the matching appointment when the table already has it', async () => {
    const deps = makeDeps({
      visitIdFromUrl: 42,
      appointmentsTableData: [
        { id: 5, patient_id: 7, visit_id: 42, patient_fio: 'SYNTHETIC-From-Table' },
      ],
    });
    renderHook(() => useDentistUrlPatient(deps as never));
    await waitFor(() => expect(deps.setSelectedPatient).toHaveBeenCalledTimes(1));
    const patient = deps.setSelectedPatient.mock.calls[0][0] as SelectedPatient;
    expect(patient.patient_name).toBe('SYNTHETIC-From-Table');
    expect(patient.visit_id).toBe(42);
    expect(deps.handleTabChange).toHaveBeenCalledWith('visit');
  });
});
