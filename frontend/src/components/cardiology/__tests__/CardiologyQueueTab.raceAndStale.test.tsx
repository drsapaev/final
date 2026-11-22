/**
 * CARDQ-FE-001/002 (audit 3886, ledger groups 3 — cardiology queue tab):
 *
 * CARDQ-FE-001 (P1): loadQueue is invoked on mount, on every queueUpdated
 *   event and by a 30s interval, and every request independently
 *   setQueue/setError/setLoading with no request epoch — a late response
 *   overwrites the newer snapshot with an obsolete patient list.
 * CARDQ-FE-002 (P2): after a failed refresh the error panel is displayed
 *   alongside the still-actionable STALE queue — call/start buttons from
 *   the previous snapshot stay enabled as if the data were current.
 *
 * Red-first: on pre-fix source both tests fail for the documented reasons.
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const queueApiMocks = vi.hoisted(() => ({
  getTodayQueue: vi.fn(),
  callPatient: vi.fn(),
  startVisit: vi.fn(),
}));

vi.mock('../../../services/queue', () => ({
  queueService: {
    getTodayQueue: queueApiMocks.getTodayQueue,
    callPatient: queueApiMocks.callPatient,
    startVisit: queueApiMocks.startVisit,
  },
}));

import CardiologyQueueTab from '../CardiologyQueueTab';
import { renderWithProviders } from '../../../test/renderWithProviders';

const noop = () => undefined;

function queueVersion(patient: string, availableActions: string[]) {
  return {
    queue_exists: true,
    doctor: { id: 7, name: 'Dr. Cardio', specialty: 'cardiology', cabinet: '101' },
    next_call_entry_id: 11,
    entries: [
      {
        id: 11,
        number: 'A001',
        patient_name: patient,
        status: 'waiting',
        available_actions: availableActions,
        can_call: availableActions.includes('call'),
        source: 'desk',
        phone: '+998901234567',
        created_at: '2026-03-30T08:00:00Z',
      },
    ],
  };
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  queueApiMocks.getTodayQueue.mockReset();
  queueApiMocks.callPatient.mockReset();
  queueApiMocks.startVisit.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe('CARDQ-FE-001: overlapping loads are ordered by request identity', () => {
  it('a late event-triggered load B is not overwritten by the older mount load A', async () => {
    const loadA = deferred<ReturnType<typeof queueVersion>>();
    queueApiMocks.getTodayQueue.mockImplementation(() => loadA.promise);

    renderWithProviders(<CardiologyQueueTab onStartVisit={noop} onOpenVisit={noop} />);

    // A (mount) is still in flight. A queueUpdated event triggers load B.
    const loadB = deferred<ReturnType<typeof queueVersion>>();
    queueApiMocks.getTodayQueue.mockImplementation(() => loadB.promise);
    await act(async () => {
      window.dispatchEvent(new CustomEvent('queueUpdated', { detail: { specialty: 'cardiology' } }));
    });

    // B resolves FIRST with the new list — B is what the user must see.
    await act(async () => {
      loadB.resolve(queueVersion('Пациент-Бэ Свежий', ['call']));
    });
    expect(await screen.findByText(/Пациент-Бэ Свежий/i)).toBeInTheDocument();

    // A resolves LAST with the obsolete list — it must be dropped.
    await act(async () => {
      loadA.resolve(queueVersion('Пациент-Альфа Старый', ['call']));
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText(/Пациент-Бэ Свежий/i)).toBeInTheDocument();
    expect(screen.queryByText(/Пациент-Альфа Старый/i)).toBeNull();
  });
});

describe('CARDQ-FE-002: a failed refresh must not leave stale actionable buttons', () => {
  it('initial success then a failed refresh — error panel visible, NO callable stale buttons', async () => {
    // Phase 1: initial load succeeds with a callable waiting ticket.
    queueApiMocks.getTodayQueue.mockResolvedValueOnce(queueVersion('Пациент-Альфа', ['call']));

    renderWithProviders(<CardiologyQueueTab onStartVisit={noop} onOpenVisit={noop} />);
    expect(await screen.findByText(/Пациент-Альфа/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /вызвать/i })).toBeInTheDocument();

    // Phase 2: the refresh fails (network / 403 / 500).
    queueApiMocks.getTodayQueue.mockRejectedValueOnce(new Error('network down'));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /обновить/i }));
    });

    // The error panel with retry must be visible…
    await waitFor(() => {
      expect(screen.getByText(/не удалось загрузить/i)).toBeInTheDocument();
    });
    // …and the stale rows must NOT expose callable/start actions anymore.
    expect(screen.queryByRole('button', { name: /вызвать/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /начать приём/i })).toBeNull();
    // The stale row itself stays visible as read-only context.
    expect(screen.getByText(/Пациент-Альфа/i)).toBeInTheDocument();

    // Phase 3: after a SUCCESSFUL refresh the actions return (backend-confirmed fresh data).
    queueApiMocks.getTodayQueue.mockResolvedValueOnce(queueVersion('Пациент-Альфа', ['call']));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /повторить/i }));
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /вызвать/i })).toBeInTheDocument();
    });
  });
});
