/**
 * PR-UI-15-1 unit contract: doctorStatus + useDoctorTabState + the
 * schedule-next view-model slice of useDoctorPanelData — all extracted
 * verbatim from DoctorPanel (registrar/cashier decomposition precedent).
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import {
  DOCTOR_PANEL_TABS,
  getAppointmentA11yContext,
  getDoctorStatusText,
  getDoctorStatusVariant,
  getPatientA11yContext,
} from '../doctorStatus';
import { useDoctorTabState } from '../useDoctorTabState';
import { useDoctorPanelData } from '../useDoctorPanelData';

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

const withRouter = (initialEntries: string[] = ['/doctor']) => {
  function RouterWrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>;
  }
  return RouterWrapper;
};

describe('doctorStatus (PR-UI-15-1)', () => {
  it('status variants: patient + appointment + queue statuses map to badge variants', () => {
    expect(getDoctorStatusVariant('active')).toBe('success');
    expect(getDoctorStatusVariant('critical')).toBe('danger');
    expect(getDoctorStatusVariant('scheduled')).toBe('primary');
    expect(getDoctorStatusVariant('in_progress')).toBe('warning');
    expect(getDoctorStatusVariant('waiting')).toBe('warning');
    expect(getDoctorStatusVariant('no_show')).toBe('danger');
    expect(getDoctorStatusVariant(undefined)).toBe('default');
    expect(getDoctorStatusVariant('unknown-status')).toBe('default');
  });

  it('status labels resolve through t() with fallback to the raw status', () => {
    expect(getDoctorStatusText('active', t)).toBe('doctor.status_active');
    expect(getDoctorStatusText('completed', t)).toBe('doctor.status_completed');
    expect(getDoctorStatusText('waiting', t)).toBe('doctor.status_waiting');
    expect(getDoctorStatusText('mystery', t)).toBe('mystery');
    expect(getDoctorStatusText(undefined, t)).toBe('');
  });

  it('a11y context builders include id + name (and time for appointments)', () => {
    expect(getPatientA11yContext({ id: 7, name: 'Ivan Petrov' })).toBe('patient Ivan Petrov (7)');
    expect(getPatientA11yContext(null)).toBe('patient patient (unknown)');
    expect(getAppointmentA11yContext({ id: 3, patientName: 'Anna', time: '10:30' })).toBe('appointment 3 for Anna at 10:30');
    expect(getAppointmentA11yContext({ id: 3, patientName: 'Anna' })).toBe('appointment 3 for Anna');
  });

  it('DOCTOR_PANEL_TABS covers the six live tabs', () => {
    expect([...DOCTOR_PANEL_TABS].sort()).toEqual(['ai', 'appointments', 'dashboard', 'patients', 'queue', 'reports']);
  });
});

describe('useDoctorTabState (PR-UI-15-1)', () => {
  it('defaults to the dashboard tab without URL params', () => {
    const { result } = renderHook(() => useDoctorTabState(), { wrapper: withRouter(['/doctor']) });
    expect(result.current.activeTab).toBe('dashboard');
    expect(result.current.searchQuery).toBe('');
    expect(result.current.filterStatus).toBe('all');
  });

  it('initial tab honors ?tab= and ?patientId= deep links', () => {
    const tab = renderHook(() => useDoctorTabState(), { wrapper: withRouter(['/doctor?tab=queue']) });
    expect(tab.result.current.activeTab).toBe('queue');

    const patient = renderHook(() => useDoctorTabState(), { wrapper: withRouter(['/doctor?patientId=42']) });
    expect(patient.result.current.activeTab).toBe('patients');
  });

  it('unknown ?tab= values fall back to dashboard', () => {
    const { result } = renderHook(() => useDoctorTabState(), { wrapper: withRouter(['/doctor?tab=hax']) });
    expect(result.current.activeTab).toBe('dashboard');
  });

  it('setDoctorTab guards unknown ids and resets search + filter (QW#2)', () => {
    const { result } = renderHook(() => useDoctorTabState(), { wrapper: withRouter(['/doctor?tab=patients']) });
    act(() => {
      result.current.setSearchQuery('pneu');
      result.current.setFilterStatus('critical');
    });

    act(() => {
      result.current.setDoctorTab('queue');
    });
    expect(result.current.activeTab).toBe('queue');
    expect(result.current.searchQuery).toBe('');
    expect(result.current.filterStatus).toBe('all');

    // Unknown tab id: no-op (guard clause, verbatim).
    act(() => {
      result.current.setDoctorTab('does-not-exist');
    });
    expect(result.current.activeTab).toBe('queue');
  });

  it('URL sync effect keeps activeTab aligned with ?tab= changes', async () => {
    const { result, rerender } = renderHook(() => useDoctorTabState(), {
      wrapper: withRouter(['/doctor?tab=patients']),
    });
    expect(result.current.activeTab).toBe('patients');
    rerender();
    await waitFor(() => expect(result.current.activeTab).toBe('patients'));
  });
});

describe('useDoctorPanelData (PR-UI-15-1)', () => {
  it('exposes the honest-empty-state lifecycle (H-08): loading cleared, no error', async () => {
    const { result } = renderHook(() =>
      useDoctorPanelData({
        t,
        setSearchQuery: vi.fn(),
        setActiveTab: vi.fn(),
        openPatientModal: vi.fn(),
      }),
      { wrapper: withRouter(['/doctor']) },
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.loadError).toBeNull();
    expect(result.current.patients).toEqual([]);
    expect(result.current.appointments).toEqual([]);
    expect(result.current.doctorSpecialty).toBe('general');
  });

  it('appointmentStats counts scheduled / in_progress / completed (M-46)', async () => {
    const { result } = renderHook(() =>
      useDoctorPanelData({
        t,
        setSearchQuery: vi.fn(),
        setActiveTab: vi.fn(),
        openPatientModal: vi.fn(),
      }),
      { wrapper: withRouter(['/doctor']) },
    );

    // Empty state: all counters at zero.
    expect(result.current.appointmentStats).toEqual({ scheduled: 0, inProgress: 0, completed: 0 });

    act(() => {
      result.current.handleScheduleNextSuccess(
        { visit_id: 'v-1', confirmation: { visit_date: '2026-09-01', visit_time: '09:00' } },
        { patient_id: 5 },
      );
    });

    expect(result.current.appointmentStats.scheduled).toBe(1);
    expect(result.current.appointmentStats.inProgress).toBe(0);
    expect(result.current.appointmentStats.completed).toBe(0);
  });

  it('handleScheduleNextSuccess prepends the scheduled appointment (DOC-05)', async () => {
    const openModal = vi.fn();
    const { result } = renderHook(() =>
      useDoctorPanelData({
        t,
        setSearchQuery: vi.fn(),
        setActiveTab: vi.fn(),
        openPatientModal: openModal,
      }),
      { wrapper: withRouter(['/doctor']) },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.handleScheduleNextSuccess(
        { visit_id: 'v-1', confirmation: { patient_name: 'Dilnoza', visit_date: '2026-09-01', visit_time: '09:00' } },
        { patient_id: 5, discount_mode: 'repeat' },
      );
    });

    expect(result.current.appointmentStats.scheduled).toBe(1);
    expect(result.current.appointments[0]).toMatchObject({
      id: 'v-1',
      patientId: 5,
      patientName: 'Dilnoza',
      status: 'scheduled',
      source: 'schedule-next',
    });
    // repeat discount mode maps to the repeat-visit label through t().
    expect(result.current.appointments[0].type).toBe('doctor.repeat_visit');
  });
});
