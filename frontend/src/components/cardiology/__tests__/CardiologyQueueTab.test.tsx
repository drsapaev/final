import '@testing-library/jest-dom';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../../test/renderWithProviders';

const { getTodayQueue, callPatient, startVisit } = vi.hoisted(() => ({
  getTodayQueue: vi.fn(),
  callPatient: vi.fn(),
  startVisit: vi.fn(),
}));

vi.mock('../../../i18n/useTranslation', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../i18n/useTranslation')>();
  return { ...actual, useTranslation: () => ({ t: (key: string) => key }) };
});
vi.mock('../../../services/queue', () => ({ queueService: { getTodayQueue, callPatient, startVisit } }));

import CardiologyQueueTab from '../CardiologyQueueTab';

describe('CardiologyQueueTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getTodayQueue.mockResolvedValue({ doctor: { id: 12, name: 'Синтетический врач' }, entries: [] });
  });

  it('shows separate loading, error, and empty states', async () => {
    getTodayQueue.mockRejectedValueOnce(new Error('offline'));
    renderWithProviders(<CardiologyQueueTab onStartVisit={vi.fn()} onOpenVisit={vi.fn()} />);

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(await screen.findByRole('alert')).toHaveTextContent('cardio.cardio_queue_error_title');
    fireEvent.click(screen.getByRole('button', { name: 'cardio.cardio_queue_retry' }));
    await waitFor(() => expect(screen.getByText('cardio.cardio_queue_empty_title')).toBeInTheDocument());
  });

  it('uses backend actions and opens a completed visit without a completion command', async () => {
    const completedEntry = {
      id: 31,
      number: 'A31',
      patient_id: 44,
      visit_id: 55,
      patient_name: 'Синтетический пациент',
      status: 'served',
      available_actions: [],
    };
    getTodayQueue.mockResolvedValue({ doctor: { id: 12, name: 'Синтетический врач' }, entries: [completedEntry] });
    const onOpenVisit = vi.fn();
    renderWithProviders(<CardiologyQueueTab onStartVisit={vi.fn()} onOpenVisit={onOpenVisit} />);

    fireEvent.click(await screen.findByRole('button', { name: /cardio\.cardio_queue_view_emr/i }));

    expect(onOpenVisit).toHaveBeenCalledWith(completedEntry, true);
    expect(screen.queryByRole('button', { name: /complete|завершить/i })).not.toBeInTheDocument();
    expect(callPatient).not.toHaveBeenCalled();
    expect(startVisit).not.toHaveBeenCalled();
  });

  it('starts a called visit and forwards canonical response identifiers', async () => {
    const calledEntry = {
      id: 30,
      number: 7,
      patient_id: null,
      visit_id: null,
      patient_name: 'Синтетический пациент',
      status: 'called',
      available_actions: ['start_visit'],
    };
    const result = { success: true, entry_id: 30, patient_id: 44, visit_id: 55 };
    getTodayQueue.mockResolvedValue({ doctor: { id: 12, name: 'Синтетический врач' }, entries: [calledEntry] });
    startVisit.mockResolvedValue(result);
    const onStartVisit = vi.fn();
    renderWithProviders(<CardiologyQueueTab onStartVisit={onStartVisit} onOpenVisit={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: 'cardio.cardio_queue_start_visit' }));

    await waitFor(() => expect(onStartVisit).toHaveBeenCalledWith(calledEntry, result));
    expect(startVisit).toHaveBeenCalledWith(30);
    expect(screen.queryByRole('button', { name: 'cardio.cardio_queue_call' })).not.toBeInTheDocument();
  });

  it('calls a waiting patient only when the backend allows the call action', async () => {
    const waitingEntry = {
      id: 29,
      number: 6,
      patient_id: 44,
      visit_id: 55,
      patient_name: 'Синтетический пациент',
      status: 'waiting',
      available_actions: ['call'],
    };
    getTodayQueue.mockResolvedValue({ doctor: { id: 12, name: 'Синтетический врач' }, entries: [waitingEntry] });
    renderWithProviders(<CardiologyQueueTab onStartVisit={vi.fn()} onOpenVisit={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: 'cardio.cardio_queue_call' }));

    await waitFor(() => expect(callPatient).toHaveBeenCalledWith(29));
    expect(startVisit).not.toHaveBeenCalled();
  });
});
