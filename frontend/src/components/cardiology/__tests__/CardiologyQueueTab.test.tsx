import '@testing-library/jest-dom';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../../test/renderWithProviders';

const { getTodayQueue, callPatient, startVisit, post } = vi.hoisted(() => ({
  getTodayQueue: vi.fn(),
  callPatient: vi.fn(),
  startVisit: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../../../i18n/useTranslation', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../i18n/useTranslation')>();
  return { ...actual, useTranslation: () => ({ t: (key: string) => key }) };
});
vi.mock('../../../services/queue', () => ({ queueService: { getTodayQueue, callPatient, startVisit } }));

vi.mock('../../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/client')>();
  return { ...actual, api: { ...actual.api, post } };
});

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

  it('pauses and resumes the same existing linked visit through server actions', async () => {
    const entry = { id: 13, number: 4, patient_id: 44, visit_id: 55, patient_name: 'SYNTHETIC', status: 'in_progress', available_actions: ['send_to_diagnostics'] };
    const paused = { ...entry, status: 'diagnostics', available_actions: ['start_visit'] };
    getTodayQueue.mockResolvedValue({ doctor: { id: 12 }, entries: [entry] });
    post.mockImplementationOnce(async () => {
      getTodayQueue.mockResolvedValue({ doctor: { id: 12 }, entries: [paused] });
      return { data: { success: true, entry_id: 13, new_status: 'diagnostics' } };
    });
    const result = { success: true, entry_id: 13, patient_id: 44, visit_id: 55 };
    startVisit.mockResolvedValueOnce(result);
    const onOpenVisit = vi.fn();
    const onStartVisit = vi.fn();
    renderWithProviders(<CardiologyQueueTab onStartVisit={onStartVisit} onOpenVisit={onOpenVisit} />);
    fireEvent.click(await screen.findByRole('button', { name: 'misc.qmc_to_diagnostics' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/queue/entry/13/diagnostics'));
    expect(await screen.findByText('cardio.cardio_queue_status_diagnostics')).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: 'cardio.cardio_queue_resume_visit' }));
    await waitFor(() => expect(onStartVisit).toHaveBeenCalledWith(paused, result));
    expect(onOpenVisit).not.toHaveBeenCalled();
    expect(startVisit).toHaveBeenCalledWith(13);
  });

  it('fails closed when a resume acknowledgement points at a different visit', async () => {
    const entry = { id: 13, number: 4, patient_id: 44, visit_id: 55, status: 'diagnostics', available_actions: ['start_visit'] };
    getTodayQueue.mockResolvedValue({ doctor: { id: 12 }, entries: [entry] });
    startVisit.mockResolvedValueOnce({ success: true, entry_id: 13, patient_id: 44, visit_id: 999 });
    const onOpenVisit = vi.fn();
    const onStartVisit = vi.fn();
    renderWithProviders(<CardiologyQueueTab onStartVisit={onStartVisit} onOpenVisit={onOpenVisit} />);
    fireEvent.click(await screen.findByRole('button', { name: 'cardio.cardio_queue_resume_visit' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(onStartVisit).not.toHaveBeenCalled();
    expect(onOpenVisit).not.toHaveBeenCalled();
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
