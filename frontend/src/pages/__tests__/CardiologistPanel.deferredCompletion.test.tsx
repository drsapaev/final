/**
 * DOCFLOW-FE-004 — the cardiology completion POST belongs to its initiating
 * queue/patient, even when an old server response arrives after switching.
 *
 * Runtime component test, not a source-string assertion. All people/visits
 * below are synthetic fixtures. No real EMR, PHI, or backend traffic.
 *
 * A success, rejection and ambiguous ACK all arrive *after* selecting B:
 * none may toast A's result, reset B, switch away from B or auto-call.
 * Positive control: a successful current A completion still resets and calls.
 */
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type TestSelection = {
  id: number;
  patient_id: number;
  visit_id: number;
  doctor_queue_entry_id: number;
  patient_name: string;
  source: string;
  status: string;
};
const A: TestSelection = {
  id: 1001, patient_id: 11, visit_id: 101,
  doctor_queue_entry_id: 1001, patient_name: 'SYNTHETIC A',
  source: 'doctor_queue', status: 'in_progress',
};
const B: TestSelection = {
  id: 2002, patient_id: 22, visit_id: 202,
  doctor_queue_entry_id: 2002, patient_name: 'SYNTHETIC B',
  source: 'doctor_queue', status: 'in_progress',
};

// The real panel owns the completion handler and selectedPatientRef.
// Only the shared navigation hook + presentational VisitTab are substituted.
const state = vi.hoisted(() => ({
  changeSelection: null as ((value: TestSelection | null) => void) | null,
  currentSelection: null as TestSelection | null,
  activeTab: 'visit',
}));

vi.mock('../../hooks/useDoctorPanelState', async () => {
  const ReactHooks = await import('react');
  return {
    useDoctorPanelState: () => {
      const [activeTab, setActiveTab] = ReactHooks.useState('visit');
      const [selectedPatient, setSelectedPatient] = ReactHooks.useState<TestSelection | null>({
        id: 1001, patient_id: 11, visit_id: 101,
        doctor_queue_entry_id: 1001, patient_name: 'SYNTHETIC A',
        source: 'doctor_queue', status: 'in_progress',
      });
      state.changeSelection = setSelectedPatient;
      state.currentSelection = selectedPatient;
      state.activeTab = activeTab;
      return {
        activeTab,
        setActiveTab,
        handleTabChange: (tab: string, beforeTransition?: () => void) => {
          beforeTransition?.();
          setActiveTab(tab);
        },
        patientIdFromUrl: null,
        visitIdFromUrl: null,
        selectedPatient,
        setSelectedPatient,
      };
    },
  };
});
vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({
    isDark: false,
    getColor: () => '#777',
    getSpacing: () => 8,
    getFontSize: () => 14,
  }),
}));
vi.mock('../../hooks/useLocalStorage', () => ({
  useLocalStorage: (_key: string, initial: unknown) => [initial, vi.fn()],
}));
vi.mock('../../hooks/useSessionTimeoutWarning', () => ({
  useSessionTimeoutWarning: () => undefined,
}));
vi.mock('../../hooks/useCardiologistHotkeys', () => ({
  useCardiologistHotkeys: () => undefined,
}));
vi.mock('../../hooks/useVisitLifecycle', () => ({
  useVisitLifecycle: () => undefined,
}));
vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock('../../components/common/ConfirmDialog', () => ({
  useConfirm: () => [async () => true, null],
}));
vi.mock('../../components/cardiology/VisitTab', () => ({
  default: (props: {
    selectedPatient: TestSelection | null;
    onComplete: (saved: Record<string, unknown>) => Promise<void>;
    loading?: boolean;
  }) => (
    <div
      data-testid="cardio-visit"
      data-patient={String(props.selectedPatient?.patient_id ?? 'none')}
      data-entry={String(props.selectedPatient?.doctor_queue_entry_id ?? 'none')}
      data-loading={String(props.loading ?? false)}
    >
      <button
        type="button"
        data-testid="cardio-complete"
        onClick={() => {
          void props.onComplete({
            complaints: 'SYNTHETIC complaint',
            diagnosis: 'SYNTHETIC diagnosis',
            icd10_code: 'R00',
            notes: 'SYNTHETIC note',
          });
        }}
      >Complete synthetic visit</button>
    </div>
  ),
}));
vi.mock('../../components/cardiology/CardiologyQueueTab', () => ({
  default: () => <div data-testid="cardio-queue" />,
}));
vi.mock('../../components/cardiology/PatientSearch', () => ({
  default: () => <div data-testid="patient-search" />,
}));
vi.mock('../../components/cardiology/ManualEcgForm', () => ({
  default: () => <div />,
}));
vi.mock('../../api/runtime', () => ({
  getApiBaseUrl: () => 'http://synthetic.invalid/api/v1',
}));
vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../utils/tokenManager', () => ({
  default: { getAccessToken: () => 'synthetic-test-only-token' },
}));
vi.mock('../../utils/logger', () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));
vi.mock('../../services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));
vi.mock('../../services/queue', () => ({
  queueService: { completeVisit: vi.fn(), callNextWaiting: vi.fn(), startVisit: vi.fn() },
}));
vi.mock('../../services/panelPrint', () => ({
  printPanelTicket: vi.fn(),
}));

import apiClient from '../../api/client';
import { queueService } from '../../services/queue';
import notify from '../../services/notify';
import CardiologistPanelUnified from '../CardiologistPanelUnified';

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function RouteQueryProbe() {
  const location = useLocation();
  return <output data-testid="cardio-route-query">{location.search}</output>;
}

async function mount() {
  render(
    <MemoryRouter initialEntries={['/doctor/cardiology?tab=visit']}>
      <CardiologistPanelUnified />
      <RouteQueryProbe />
    </MemoryRouter>,
  );
  await screen.findByTestId('cardio-visit');
  expect(screen.getByTestId('cardio-visit').getAttribute('data-patient')).toBe('11');
}

async function switchToB() {
  await act(async () => {
    state.changeSelection?.(B);
  });
  await waitFor(() => {
    expect(screen.getByTestId('cardio-visit').getAttribute('data-patient')).toBe('22');
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  state.changeSelection = null;
  state.currentSelection = null;
  state.activeTab = 'visit';
  vi.mocked(apiClient.get).mockImplementation(async (url: unknown) => {
    if (url === '/doctor/my-info') return { data: { doctor: { id: 1 } } } as never;
    if (url === '/registrar/queues/today') return { data: { queues: [] } } as never;
    return { data: {} } as never;
  });
  vi.mocked(queueService.callNextWaiting).mockResolvedValue({ success: false } as never);
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: false,
    status: 404,
    json: async () => ({}),
  })));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('DOCFLOW-FE-004 — deferred cardiology completion ACK respects live selection', () => {
  it.each([
    { label: 'success', response: { success: true } },
    { label: 'rejected', response: { success: false, message: 'SYNTHETIC A rejected' } },
    { label: 'ambiguous', response: { success: false, unknown: true, message: 'SYNTHETIC A ambiguous' } },
  ])('drops a late $label A reply after selecting B, without B UI/reset/toast or auto-call', async ({ response }) => {
    const held = deferred<typeof response>();
    vi.mocked(queueService.completeVisit).mockReturnValue(held.promise as never);
    await mount();
    vi.mocked(notify.success).mockClear();
    vi.mocked(notify.error).mockClear();

    fireEvent.click(screen.getByTestId('cardio-complete'));
    await waitFor(() => expect(queueService.completeVisit).toHaveBeenCalledWith(
      A.doctor_queue_entry_id,
      expect.objectContaining({ patient_id: A.patient_id }),
    ));

    await switchToB();
    const backgroundGetCalls = vi.mocked(apiClient.get).mock.calls.length;
    await act(async () => {
      held.resolve(response);
      await held.promise;
      await Promise.resolve();
    });

    expect(state.currentSelection?.patient_id).toBe(B.patient_id);
    expect(state.activeTab).toBe('visit');
    expect(screen.getByTestId('cardio-route-query').textContent).toContain('tab=visit');
    expect(screen.getByTestId('cardio-visit').getAttribute('data-patient')).toBe('22');
    expect(screen.getByTestId('cardio-visit').getAttribute('data-entry')).toBe('2002');
    // An old A completion must not leave B's controls permanently busy.
    expect(screen.getByTestId('cardio-visit').getAttribute('data-loading')).toBe('false');
    expect(vi.mocked(notify.success)).not.toHaveBeenCalled();
    expect(vi.mocked(notify.error)).not.toHaveBeenCalled();
    expect(queueService.callNextWaiting).not.toHaveBeenCalled();
    // An old ambiguous A ACK must not initiate B-context reconciliation.
    if (response.unknown === true) {
      expect(vi.mocked(apiClient.get).mock.calls.length).toBe(backgroundGetCalls);
    }
  });

  it('drops a late network rejection from A after switching to B, without an A error toast', async () => {
    const held = deferred<{ success: boolean }>();
    vi.mocked(queueService.completeVisit).mockReturnValue(held.promise as never);
    await mount();
    vi.mocked(notify.error).mockClear();
    vi.mocked(notify.success).mockClear();

    fireEvent.click(screen.getByTestId('cardio-complete'));
    await waitFor(() => expect(queueService.completeVisit).toHaveBeenCalledTimes(1));
    await switchToB();

    await act(async () => {
      held.reject(new Error('SYNTHETIC failed A transport'));
      await held.promise.catch(() => undefined);
      await Promise.resolve();
    });

    expect(state.currentSelection?.patient_id).toBe(22);
    expect(state.activeTab).toBe('visit');
    expect(screen.getByTestId('cardio-route-query').textContent).toContain('tab=visit');
    expect(screen.getByTestId('cardio-visit').getAttribute('data-patient')).toBe('22');
    expect(screen.getByTestId('cardio-visit').getAttribute('data-loading')).toBe('false');
    expect(vi.mocked(notify.error)).not.toHaveBeenCalled();
    expect(vi.mocked(notify.success)).not.toHaveBeenCalled();
    expect(queueService.callNextWaiting).not.toHaveBeenCalled();
  });

  it('positive control: the current visit A still finishes on an explicit success ACK', async () => {
    const held = deferred<{ success: boolean }>();
    vi.mocked(queueService.completeVisit).mockReturnValue(held.promise as never);
    await mount();
    vi.mocked(notify.success).mockClear();
    vi.mocked(notify.error).mockClear();

    fireEvent.click(screen.getByTestId('cardio-complete'));
    await waitFor(() => expect(queueService.completeVisit).toHaveBeenCalledTimes(1));
    await act(async () => {
      held.resolve({ success: true });
      await held.promise;
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(state.currentSelection).toBeNull();
      expect(state.activeTab).toBe('queue');
      expect(screen.getByTestId('cardio-route-query').textContent).toContain('tab=queue');
    });
    expect(vi.mocked(notify.success)).toHaveBeenCalledWith('cardio.visit_completed');
    expect(vi.mocked(notify.error)).not.toHaveBeenCalled();
    expect(queueService.callNextWaiting).toHaveBeenCalledTimes(1);
  });
});
