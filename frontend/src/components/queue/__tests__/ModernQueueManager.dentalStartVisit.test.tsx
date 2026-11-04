import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '../../../contexts/ThemeContext';

const queueMocks = vi.hoisted(() => ({
  callNextPatientInQueue: vi.fn(),
  loadQueueSnapshot: vi.fn(async () => ({ entries: [], is_open: true })),
  specialists: [{ id: '7', full_name: 'Registrar test doctor', specialty: 'cardiology' }],
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

import ModernQueueManager from '../ModernQueueManager';

describe('ModernQueueManager dentist start-visit flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queueMocks.callNextPatientInQueue.mockResolvedValue({
      success: true,
      patient: { id: 42, name: 'Synthetic patient', number: 6 },
    });
    queueMocks.loadQueueSnapshot.mockResolvedValue({ entries: [], is_open: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('stores the selected registrar doctor ID and loads that doctor queue', async () => {
    const user = userEvent.setup();
    const onDoctorChange = vi.fn();

    render(
      <ThemeProvider>
        <ModernQueueManager
          mode="registrar"
          doctors={[{ id: '7', full_name: 'Registrar test doctor', specialty: 'cardiology' }]}
          onDoctorChange={onDoctorChange}
        />
      </ThemeProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'misc.mqm_select_doctor' }));
    await user.click(screen.getByRole('option', { name: 'Registrar test doctor • cardiology' }));

    expect(onDoctorChange).toHaveBeenCalledWith('7');
    expect(screen.getByText('Registrar test doctor • cardiology')).toBeInTheDocument();
    await waitFor(() => {
      expect(queueMocks.loadQueueSnapshot).toHaveBeenCalledWith({
        specialistId: '7',
        targetDate: expect.any(String),
        doctor: { id: '7', full_name: 'Registrar test doctor', specialty: 'cardiology' },
      });
    });
  });

  it('keeps call-next as the queue command and offers a separate manager-level start action', async () => {
    const onStartVisit = vi.fn(async () => true);
    render(
      <ThemeProvider>
        <ModernQueueManager
          mode="doctor"
          selectedDoctor="7"
          doctors={[{ id: '7', specialty: 'dentistry' }]}
          onStartVisit={onStartVisit}
        />
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'misc.mqm_call' }));
    const startVisitButton = await screen.findByRole('button', { name: 'dental.dental_panel_start_visit_for' });

    expect(queueMocks.callNextPatientInQueue).toHaveBeenCalledWith({ specialistId: '7', targetDate: expect.any(String) });
    expect(onStartVisit).not.toHaveBeenCalled();
    expect(screen.getByText('Synthetic patient · №6')).toBeInTheDocument();

    fireEvent.click(startVisitButton);
    await waitFor(() => expect(onStartVisit).toHaveBeenCalledWith({ id: 42, name: 'Synthetic patient', number: 6 }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'dental.dental_panel_start_visit_for' })).toBeNull());
  });

  it('keeps the called patient available for retry when starting the visit fails', async () => {
    const onStartVisit = vi.fn(async () => false);
    render(
      <ThemeProvider>
        <ModernQueueManager
          mode="doctor"
          selectedDoctor="7"
          doctors={[{ id: '7', specialty: 'dentistry' }]}
          onStartVisit={onStartVisit}
        />
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'misc.mqm_call' }));
    const startVisitButton = await screen.findByRole('button', { name: 'dental.dental_panel_start_visit_for' });
    fireEvent.click(startVisitButton);

    await waitFor(() => expect(onStartVisit).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole('button', { name: 'dental.dental_panel_start_visit_for' })).toBeEnabled();
  });

  // REG-FE-068: the doctor Select offers a '' placeholder option, so
  // deselecting is a real user action — it must reach loadQueueSnapshot as
  // an explicit clear transition (the hook then drops the queue snapshot and
  // invalidates any in-flight request of the deselected doctor). Pre-fix,
  // loadQueue returned early on an empty selection and the deselected
  // doctor's queue stayed on screen.
  it('REG-FE-068: deselecting the doctor issues a clear transition instead of keeping the last queue', async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider>
        <ModernQueueManager
          mode="registrar"
          doctors={[{ id: '7', full_name: 'Registrar test doctor', specialty: 'cardiology' }]}
        />
      </ThemeProvider>,
    );

    // Select the doctor first.
    await user.click(screen.getByRole('button', { name: 'misc.mqm_select_doctor' }));
    await user.click(screen.getByRole('option', { name: 'Registrar test doctor • cardiology' }));
    await waitFor(() => {
      expect(queueMocks.loadQueueSnapshot).toHaveBeenCalledWith(expect.objectContaining({ specialistId: '7' }));
    });

    // Deselect back to the placeholder option.
    await user.click(screen.getByRole('button', { name: 'misc.mqm_select_doctor' }));
    await user.click(screen.getByRole('option', { name: 'misc.mqm_select_doctor' }));

    await waitFor(() => {
      expect(queueMocks.loadQueueSnapshot).toHaveBeenCalledWith(expect.objectContaining({ specialistId: '' }));
    });
  });

  // #3856 review follow-up (controlled vs uncontrolled): when the parent
  // passes `selectedDoctor`, the prop is authoritative INCLUDING the empty
  // string. Pre-fix, a parent-driven reset to '' fell back to the last
  // internal UI choice, so the deselected doctor's queue stayed on screen.
  it('a parent-driven reset of the controlled selection to "" clears the doctor instead of falling back to the internal choice', async () => {
    const user = userEvent.setup();
    const onDoctorChange = vi.fn();
    const doctors = [{ id: '7', full_name: 'Registrar test doctor', specialty: 'cardiology' }];

    // Controlled mode with the parent's initial empty selection (QueueView
    // passes searchParams.get('doctor') || '').
    const { rerender } = render(
      <ThemeProvider>
        <ModernQueueManager
          mode="registrar"
          selectedDoctor=""
          doctors={doctors}
          onDoctorChange={onDoctorChange}
        />
      </ThemeProvider>,
    );

    // The user picks a doctor through the UI — the internal state now holds
    // '7' (the fallback source of the bug)…
    await user.click(screen.getByRole('button', { name: 'misc.mqm_select_doctor' }));
    await user.click(screen.getByRole('option', { name: 'Registrar test doctor • cardiology' }));
    // …and the parent echoes the choice back through the controlled prop
    // (exactly what QueueView does by writing the `doctor` URL param). In
    // controlled mode only the echoed prop drives the snapshot load.
    rerender(
      <ThemeProvider>
        <ModernQueueManager
          mode="registrar"
          selectedDoctor="7"
          doctors={doctors}
          onDoctorChange={onDoctorChange}
        />
      </ThemeProvider>,
    );
    await waitFor(() => {
      expect(queueMocks.loadQueueSnapshot).toHaveBeenCalledWith(expect.objectContaining({ specialistId: '7' }));
    });

    // From here on only the RESET transition matters: clear the recorded
    // mount/selection calls so an assertion on '' cannot be satisfied by
    // the initial empty-selection load.
    queueMocks.loadQueueSnapshot.mockClear();

    // The parent resets the controlled selection to '' (e.g. a "clear
    // filters" action or a URL param cleanup). The prop must win over the
    // internal choice.
    rerender(
      <ThemeProvider>
        <ModernQueueManager
          mode="registrar"
          selectedDoctor=""
          doctors={doctors}
          onDoctorChange={onDoctorChange}
        />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(queueMocks.loadQueueSnapshot).toHaveBeenCalledWith(expect.objectContaining({ specialistId: '' }));
    });
    // The Select shows the placeholder again, not the stale doctor.
    expect(screen.getByRole('button', { name: 'misc.mqm_select_doctor' })).toBeInTheDocument();
  });
});
