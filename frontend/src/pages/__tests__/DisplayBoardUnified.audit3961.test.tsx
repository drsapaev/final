import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const wsMock = vi.hoisted(() => ({
  openDisplayBoardWS: vi.fn(),
}));

const apiMock = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
  },
}));

vi.mock('../../api/client', () => apiMock);
vi.mock('../../api/ws', () => wsMock);
vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light' }),
}));
vi.mock('../../utils/logger', () => ({
  default: {
    log: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

import DisplayBoardUnified from '../DisplayBoardUnified';

// SYNTHETIC fixtures only (audit PR #3961): no real patient/staff identities.
describe('DisplayBoardUnified audit-3961 frontend plane', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.clearAllMocks();
    (window.localStorage.getItem as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue(null);
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window, 'AudioContext', {
      writable: true,
      configurable: true,
      value: undefined,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const renderBoard = async (props: Record<string, unknown> = {}) => {
    apiMock.api.get.mockResolvedValue({
      data: {
        department: 'Reg',
        date_str: '2026-05-23',
        is_open: true,
        last_ticket: 0,
      },
    });
    let wsMessageHandler: ((data: unknown) => void) | null = null;
    wsMock.openDisplayBoardWS.mockImplementation(
      (_boardId: string, onMessage: (data: unknown) => void, onConnect?: () => void) => {
        wsMessageHandler = onMessage;
        onConnect?.();
        return vi.fn();
      }
    );
    const view = render(
      <DisplayBoardUnified
        department="Reg"
        dateStr="2026-05-23"
        boardId="main_board"
        refreshMs={60000}
        {...props}
      />
    );
    await waitFor(() => {
      expect(apiMock.api.get).toHaveBeenCalled();
    });
    return {
      view,
      push: (msg: unknown) => act(() => { wsMessageHandler!(msg); }),
    };
  };

  // DISPLAYCALL-FE-001: the highlighted last call expires per the
  // backend-owned display_duration and clears on a real lifecycle update.
  it('clears the highlighted call after display_duration expires', async () => {
    const { push } = await renderBoard();

    push({
      type: 'patient_call',
      data: { queue_number: 11, patient_name: 'Synthetic Patient 11', display_duration: 5 },
    });
    const callNumber = () => screen.getByText(/№\s*11/);
    expect(callNumber()).toBeInTheDocument();

    // Still highlighted before the window passes.
    act(() => { vi.advanceTimersByTime(4999); });
    expect(callNumber()).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(1); });
    expect(screen.queryByText(/№\s*11/)).not.toBeInTheDocument();
  });

  it('clears the highlighted call when the entry reaches a terminal status', async () => {
    const { push } = await renderBoard();

    push({
      type: 'patient_call',
      data: { queue_number: 11, patient_name: 'Synthetic Patient 11', display_duration: 300 },
    });
    expect(screen.getByText(/№\s*11/)).toBeInTheDocument();

    // Backend-formatted scoped update: entry 11 is now served.
    push({
      type: 'queue_update',
      event_type: 'queue.updated',
      data: {
        queue_id: 1,
        queue_entries: [
          { id: 11, queue_id: 1, number: 11, patient_name: 'Synthetic Patient 11', status: 'served', created_at: '2026-05-23T08:00:00' },
        ],
      },
    });

    expect(screen.queryByText(/№\s*11/)).not.toBeInTheDocument();
  });

  // DISPLAYANNOUNCE-FE-001: each announcement lives its requested
  // display_duration window, independently of newer events.
  it('removes an announcement when its display_duration passes', async () => {
    const { push } = await renderBoard();

    push({
      type: 'announcement',
      data: { text: 'Synthetic warning', announcement_type: 'warning', created_at: 'a1', display_duration: 5 },
    });
    push({
      type: 'announcement',
      data: { text: 'Synthetic info', announcement_type: 'info', created_at: 'a2', display_duration: 60 },
    });

    expect(screen.getByText(/Synthetic warning/)).toBeInTheDocument();
    expect(screen.getByText(/Synthetic info/)).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(5000); });
    expect(screen.queryByText(/Synthetic warning/)).not.toBeInTheDocument();
    // The second notice keeps its own independent timer.
    expect(screen.getByText(/Synthetic info/)).toBeInTheDocument();
  });

  // DISPLAYERROR-FE-001: a backend failure snapshot is a visible error,
  // never a live-looking empty board; last good rows are kept.
  it('shows a visible error banner on an error snapshot and keeps last good rows', async () => {
    const { push } = await renderBoard();

    push({
      type: 'initial_state',
      data: {
        queue_entries: [
          { id: 1, number: 7, patient_name: 'Synthetic Patient 7', status: 'waiting', created_at: '2026-05-23T08:00:00' },
        ],
        current_call: null,
        announcements: [],
      },
    });
    expect(await screen.findByText('7')).toBeInTheDocument();

    push({
      type: 'initial_state',
      data: { queue_entries: [], current_call: null, announcements: [], error: 'Ошибка загрузки данных' },
    });

    expect(screen.getByTestId('dbu-snapshot-error')).toBeInTheDocument();
    // Last good rows are retained, not wiped into a fake empty board.
    expect(screen.getByText('7')).toBeInTheDocument();

    // A successful snapshot clears the error banner (positive control).
    push({
      type: 'initial_state',
      data: { queue_entries: [], current_call: null, announcements: [] },
    });
    expect(screen.queryByTestId('dbu-snapshot-error')).not.toBeInTheDocument();
  });

  // DISPLAYAUDIO-FE-001: an explicit soundInitial=false applies on the
  // first render and the manual mute survives the periodic stats refresh.
  it('honors soundInitial=false and keeps the manual mute across refreshes', async () => {
    const { push } = await renderBoard({ soundInitial: false });

    // The sound toggle starts muted (VolumeX icon): aria-label is the
    // "turn sound ON" title when currently muted.
    const soundButton = () =>
      screen.queryByRole('button', { name: /включить звук|enable sound/i });
    expect(soundButton()).not.toBeNull();

    // Manual unmute, then a REST refresh arrives with sound_default=true —
    // the session override must survive the poll.
    await userEvent.click(soundButton()!);
    expect(screen.queryByRole('button', { name: /включить звук|enable sound/i })).toBeNull();

    push({ type: 'initial_state', data: { queue_entries: [], current_call: null, announcements: [] } });
    const before = apiMock.api.get.mock.calls.length;
    act(() => { vi.advanceTimersByTime(61000); });
    expect(apiMock.api.get.mock.calls.length).toBeGreaterThan(before);
    // Still unmuted — the poll did not reset the manual choice.
    expect(screen.queryByRole('button', { name: /включить звук|enable sound/i })).toBeNull();
  });
});
