/**
 * QMAN-FE-001 / QMAN-FE-002 (audit 3886, ledger group «manager called-patient
 * state and WebSocket reconnect»): ModernQueueManager selection identity.
 *
 * - QMAN-FE-002: the local `calledPatients` list is owned by ONE
 *   doctor/date selection. A selection transition (doctor A → B, or a new
 *   target date) must invalidate the list — entries called under A must not
 *   expose Start Visit actions under B. A pending call-next response for A
 *   that resolves only after the switch to B must not append A's patient to
 *   B's list.
 * - QMAN-FE-001 (UI half): a failed load of the CURRENT selection surfaces a
 *   visible recoverable error with a retry action instead of silently
 *   keeping another selection's queue on screen (the hook-level fail-closed
 *   clearing is pinned in useQueueManager.snapshot.test.ts).
 *
 * Red-first: on pre-fix source the identity cases fail (A's entry keeps its
 * Start Visit button under B; the stale response appends to B's list) and
 * no load-error banner exists.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '../../../contexts/ThemeContext';

const queueMocks = vi.hoisted(() => ({
  callNextPatientInQueue: vi.fn(),
  loadQueueSnapshot: vi.fn(async () => ({ entries: [], is_open: true })),
  specialists: [{ id: '7', full_name: 'Doctor A', specialty: 'cardiology' }],
  generateDoctorQRCode: vi.fn(),
  generateClinicQRCode: vi.fn(),
  openReceptionForDoctor: vi.fn(),
  closeReceptionForDoctor: vi.fn(),
  setQrData: vi.fn(),
}));

vi.mock('../../../hooks/useQueueManager', () => ({
  useQueueManager: () => ({
    loading: false,
    queueData: { entries: [], is_open: true },
    statistics: null,
    qrData: null,
    specialists: queueMocks.specialists,
    loadQueueSnapshot: queueMocks.loadQueueSnapshot,
    generateDoctorQRCode: queueMocks.generateDoctorQRCode,
    generateClinicQRCode: queueMocks.generateClinicQRCode,
    openReceptionForDoctor: queueMocks.openReceptionForDoctor,
    closeReceptionForDoctor: queueMocks.closeReceptionForDoctor,
    callNextPatientInQueue: queueMocks.callNextPatientInQueue,
    setQrData: queueMocks.setQrData,
  }),
}));

vi.mock('../../../hooks/useQueueWebSocket', () => ({
  useQueueWebSocket: () => ({ state: 'disconnected' }),
}));

vi.mock('../../common/ConfirmDialog', () => ({
  useConfirm: () => [vi.fn(async () => true), null],
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

import ModernQueueManager from '../ModernQueueManager';

const DOCTORS = [
  { id: '7', full_name: 'Doctor A', specialty: 'cardiology' },
  { id: '3', full_name: 'Doctor B', specialty: 'cardiology' },
];

const CALLED_PATIENT = { id: 42, name: 'Synthetic patient', number: 6 };

function renderManager(props: Record<string, unknown> = {}) {
  return render(
    <ThemeProvider>
      <ModernQueueManager
        mode="doctor"
        doctors={DOCTORS}
        selectedDoctor="7"
        selectedDate="2026-11-03"
        onStartVisit={vi.fn(async () => true)}
        {...props}
      />
    </ThemeProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  queueMocks.loadQueueSnapshot.mockResolvedValue({ entries: [], is_open: true });
  queueMocks.callNextPatientInQueue.mockResolvedValue({
    success: true,
    patient: CALLED_PATIENT,
  });
});

afterEach(() => {
  vi.useRealTimers();
});

async function callNextPatient() {
  const user = userEvent.setup();
  const callButton = await screen.findByRole('button', { name: 'misc.mqm_call' });
  await user.click(callButton);
  await waitFor(() => expect(queueMocks.callNextPatientInQueue).toHaveBeenCalledTimes(1));
}

describe('QMAN-FE-002: called-patient list is owned by the current doctor/date selection', () => {
  it('a called entry for doctor A disappears when the selection switches to doctor B', async () => {
    const { rerender } = renderManager();
    await callNextPatient();

    // X was called under doctor A and shows a Start Visit action.
    expect(await screen.findByRole('button', { name: /dental\.dental_panel_start_visit/ }))
      .toBeTruthy();

    // The parent moves the selection to doctor B (in-place, no remount).
    rerender(
      <ThemeProvider>
        <ModernQueueManager
          mode="doctor"
          doctors={DOCTORS}
          selectedDoctor="3"
          selectedDate="2026-11-03"
          onStartVisit={vi.fn(async () => true)}
        />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /dental\.dental_panel_start_visit/ }))
        .toBeNull();
    });
    expect(screen.queryByText(/Synthetic patient/)).toBeNull();
  });

  it('a called entry for date D disappears when the selection switches to D+1 (same doctor)', async () => {
    const { rerender } = renderManager();
    await callNextPatient();
    expect(await screen.findByRole('button', { name: /dental\.dental_panel_start_visit/ }))
      .toBeTruthy();

    rerender(
      <ThemeProvider>
        <ModernQueueManager
          mode="doctor"
          doctors={DOCTORS}
          selectedDoctor="7"
          selectedDate="2026-11-04"
          onStartVisit={vi.fn(async () => true)}
        />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /dental\.dental_panel_start_visit/ }))
        .toBeNull();
    });
  });

  it('a pending call-next for A that resolves only after the switch to B never appends to B\'s list', async () => {
    let resolveCall!: (value: { success: boolean; patient: typeof CALLED_PATIENT }) => void;
    queueMocks.callNextPatientInQueue.mockImplementation(
      () => new Promise((resolve) => { resolveCall = resolve; }),
    );

    const { rerender } = renderManager();
    const user = userEvent.setup();
    const callButton = await screen.findByRole('button', { name: 'misc.mqm_call' });
    await user.click(callButton);
    await waitFor(() => expect(queueMocks.callNextPatientInQueue).toHaveBeenCalledTimes(1));

    // Selection moves to doctor B while A's call-next is still pending.
    rerender(
      <ThemeProvider>
        <ModernQueueManager
          mode="doctor"
          doctors={DOCTORS}
          selectedDoctor="3"
          selectedDate="2026-11-03"
          onStartVisit={vi.fn(async () => true)}
        />
      </ThemeProvider>,
    );

    resolveCall({ success: true, patient: CALLED_PATIENT });
    await waitFor(() => expect(queueMocks.loadQueueSnapshot).toHaveBeenCalled());

    // The stale A response must not surface X under doctor B.
    expect(screen.queryByRole('button', { name: /dental\.dental_panel_start_visit/ }))
      .toBeNull();
    expect(screen.queryByText(/Synthetic patient/)).toBeNull();
  });

  it('positive control: the same selection keeps the called entry and its Start Visit action', async () => {
    const onStartVisit = vi.fn(async () => true);
    renderManager({ onStartVisit });
    await callNextPatient();

    const startButton = await screen.findByRole('button', { name: /dental\.dental_panel_start_visit/ });
    const user = userEvent.setup();
    await user.click(startButton);

    await waitFor(() => expect(onStartVisit).toHaveBeenCalledWith(CALLED_PATIENT));
  });
});

describe('QMAN-FE-001 (UI half): a failed current-selection load surfaces a recoverable error', () => {
  it('shows an error banner with a retry action when the current selection fails to load', async () => {
    queueMocks.loadQueueSnapshot.mockRejectedValue(new Error('network down'));
    renderManager();

    const banner = await screen.findByRole('alert');
    // Localized headline + the raw failure detail; retry targets the
    // canonical snapshot load for the current selection.
    expect(banner.textContent).toContain('misc.mqm_queue_load_failed');
    expect(banner.textContent).toContain('network down');

    const user = userEvent.setup();
    const retryButton = screen.getByRole('button', { name: 'misc.mqm_retry_load' });
    await user.click(retryButton);
    await waitFor(() => expect(queueMocks.loadQueueSnapshot.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('keeps the localized headline even for a non-Error rejection reason', async () => {
    queueMocks.loadQueueSnapshot.mockRejectedValue(undefined);
    renderManager();

    const banner = await screen.findByRole('alert');
    expect(banner.textContent).toContain('misc.mqm_queue_load_failed');
  });

  it('positive control: a successful load shows no error banner', async () => {
    renderManager();
    await waitFor(() => expect(queueMocks.loadQueueSnapshot).toHaveBeenCalled());
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
