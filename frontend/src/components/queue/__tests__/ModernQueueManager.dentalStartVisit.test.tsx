import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '../../../contexts/ThemeContext';

const queueMocks = vi.hoisted(() => ({
  callNextPatientInQueue: vi.fn(),
  loadQueueSnapshot: vi.fn(async () => ({ entries: [], is_open: true })),
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
    specialists: [],
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
});
