/**
 * PR-UI-15-2 unit contract: doctorViewmodel pure filters + view smoke
 * renders (verbatim extraction from DoctorPanel — registrar/cashier
 * decomposition precedent).
 */
import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '../../../test/renderWithProviders';
import { filterAppointments, filterPatients } from '../doctorViewmodel';
import type { AppointmentDto, PatientRecord } from '../doctorStatus';
import DoctorEmptyState from '../views/DoctorEmptyState';
import DoctorDashboardTab from '../views/DoctorDashboardTab';
import DoctorTabsNav from '../views/DoctorTabsNav';
import DoctorPatientInfo from '../views/DoctorPatientInfo';

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

describe('doctorViewmodel (PR-UI-15-2)', () => {
  const patients: PatientRecord[] = [
    { id: 1, name: 'SYNTHETIC-Patient-One', phone: 'SYNTHETIC-PHONE-1', status: 'active' },
    { id: 2, name: 'SYNTHETIC-Patient-Two', phone: 'SYNTHETIC-PHONE-2', status: 'critical' },
  ];

  it('filterPatients matches by name (case-insensitive) or phone', () => {
    expect(filterPatients(patients, 'synthetic-patient-one', 'all')).toHaveLength(1);
    expect(filterPatients(patients, 'SYNTHETIC-PATIENT-ONE', 'all')).toHaveLength(1);
    expect(filterPatients(patients, 'SYNTHETIC-PHONE-2', 'all')).toHaveLength(1);
    expect(filterPatients(patients, 'no-match', 'all')).toHaveLength(0);
  });

  it('filterPatients applies the status filter and passes all through', () => {
    expect(filterPatients(patients, '', 'all')).toHaveLength(2);
    expect(filterPatients(patients, '', 'critical')).toHaveLength(1);
    expect(filterPatients(patients, '', 'recovery')).toHaveLength(0);
  });

  it('filterPatients combines search AND status', () => {
    expect(filterPatients(patients, 'two', 'critical')).toHaveLength(1);
    expect(filterPatients(patients, 'two', 'active')).toHaveLength(0);
  });

  it('filterAppointments matches by patient name + status', () => {
    const appointments: AppointmentDto[] = [
      { id: 1, patientName: 'SYNTHETIC-Patient-One', status: 'scheduled' },
      { id: 2, patientName: 'SYNTHETIC-Patient-Two', status: 'completed' },
    ];
    expect(filterAppointments(appointments, 'two', 'all')).toHaveLength(1);
    expect(filterAppointments(appointments, '', 'completed')).toHaveLength(1);
    expect(filterAppointments(appointments, '', 'cancelled')).toHaveLength(0);
    expect(filterAppointments(appointments, 'one', 'completed')).toHaveLength(0);
  });
});

describe('doctor views (PR-UI-15-2)', () => {
  it('DoctorEmptyState renders icon, title, description and action', () => {
    renderWithProviders(
      <DoctorEmptyState
        icon={() => <span data-testid="icon" />}
        title="Нет пациентов"
        description="Попробуйте изменить фильтры"
        action={<button>Повторить</button>}
      />,
    );
    expect(screen.getByText('Нет пациентов')).toBeInTheDocument();
    expect(screen.getByText('Попробуйте изменить фильтры')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeInTheDocument();
  });

  it('DoctorDashboardTab renders the four stat cards', () => {
    // Minimal styles stub — the verbatim styles hook needs ThemeContext;
    // the smoke render verifies the stats wiring, not the theming.
    const styles = {
      dashboardGridStyle: {}, statCardStyle: {}, statCardHoverStyle: {},
      primaryColor: '#000', successColor: '#000', warningColor: '#000', accentColor: '#000',
      getColor: () => '#000', getShadow: () => 'none',
    } as unknown as Parameters<typeof DoctorDashboardTab>[0]['styles'];
    renderWithProviders(
      <DoctorDashboardTab
        patientsCount={4}
        appointmentStats={{ scheduled: 3, inProgress: 2, completed: 1 }}
        styles={styles}
      />,
    );
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('Активных пациентов')).toBeInTheDocument();
    expect(screen.getByText('Записей на сегодня')).toBeInTheDocument();
  });

  it('DoctorTabsNav renders six tabs with the queue badge when waiting > 0', () => {
    const styles = {
      isMobile: false, tabsStyle: {}, tabStyle: {}, activeTabStyle: {},
      interactiveSurface: 'var(--mac-nav-item-bg)', interactiveSurfaceHover: 'var(--mac-card-hover-bg)',
    } as unknown as Parameters<typeof DoctorTabsNav>[0]['styles'];
    renderWithProviders(
      <DoctorTabsNav
        activeTab="queue"
        setDoctorTab={vi.fn()}
        queueStatsWaiting={3}
        styles={styles}
        t={t}
      />,
    );
    expect(screen.getAllByRole('button')).toHaveLength(6);
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('DoctorPatientInfo renders patient info and closes via the close button', () => {
    const onClose = vi.fn();
    renderWithProviders(
      <DoctorPatientInfo
        patient={{ id: 7, name: 'SYNTHETIC-Patient-Seven', phone: 'SYNTHETIC-PHONE-7', age: 30, status: 'active' }}
        onClose={onClose}
        t={t}
      />,
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('SYNTHETIC-Patient-Seven')).toBeInTheDocument();
    expect(screen.getByText('SYNTHETIC-PHONE-7')).toBeInTheDocument();
    screen.getByRole('button', { name: 'doctor.aria_close_patient_info' }).click();
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
