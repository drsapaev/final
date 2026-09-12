import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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

import DisplayBoardUnified, { resolveBoardEntryKey } from '../DisplayBoardUnified';

// SYNTHETIC fixtures only (RQ-24.a.2): no real patient/staff identities.
describe('DisplayBoardUnified contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (window.localStorage.getItem as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue(null);
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  });

  it('treats /board/state as stats-only and uses websocket initial_state for live rows', async () => {
    let wsMessageHandler: ((data: unknown) => void) | null;
    apiMock.api.get.mockResolvedValueOnce({
      data: {
        department: 'Reg',
        date_str: '2026-05-23',
        is_open: true,
        start_number: 1,
        last_ticket: 17,
        waiting: 4,
        serving: 2,
        done: 1,
        queue_entries: [
          { number: 99, patient_name: 'REST Patient', status: 'waiting' },
        ],
        current_call: { queue_number: 99, patient_name: 'REST Call' },
        announcements: [{ text: 'REST Announcement', created_at: 'rest' }],
      },
    });
    wsMock.openDisplayBoardWS.mockImplementation((_boardId, onMessage, onConnect) => {
      wsMessageHandler = onMessage;
      onConnect?.();
      return vi.fn();
    });

    render(
      <DisplayBoardUnified
        department="Reg"
        dateStr="2026-05-23"
        boardId="main_board"
        refreshMs={60000}
      />
    );

    await waitFor(() => {
      expect(apiMock.api.get).toHaveBeenCalledWith('/board/state', {
        params: { department: 'Reg', date: '2026-05-23' },
      });
    });
    expect(screen.getByText('17')).toBeInTheDocument();
    expect(screen.queryByText('REST Patient')).not.toBeInTheDocument();
    expect(screen.queryByText('REST Call')).not.toBeInTheDocument();
    expect(screen.queryByText(/REST Announcement/)).not.toBeInTheDocument();

    act(() => {
      wsMessageHandler!({
        type: 'initial_state',
        data: {
          queue_entries: [
            { number: 5, patient_name: 'WS Patient', status: 'waiting', created_at: '2026-05-23T08:00:00' },
          ],
          current_call: {
            queue_number: 5,
            patient_name: 'WS Call',
            doctor_name: 'Dr. Socket',
          },
          announcements: [
            { text: 'WS Announcement', created_at: 'ws', announcement_type: 'info' },
          ],
        },
      });
    });

    expect(await screen.findByText('WS Call')).toBeInTheDocument();
    expect(screen.getByText(/WS Announcement/)).toBeInTheDocument();
  });
});

// RQ-24.a.2: rows must be distinguishable across queues sharing one board
// (cabinet/owner/specialty from WS payload) and keyed stably (no duplicate
// React keys when two queues have equal ticket numbers).
describe('DisplayBoardUnified row distinctness (RQ-24.a.2)', () => {
  const renderBoard = async () => {
    apiMock.api.get.mockResolvedValueOnce({
      data: {
        department: 'Reg',
        date_str: '2026-05-23',
        is_open: true,
        last_ticket: 0,
      },
    });
    let wsMessageHandler: ((data: unknown) => void) | null = null;
    wsMock.openDisplayBoardWS.mockImplementation((_boardId: string, onMessage: (data: unknown) => void, onConnect?: () => void) => {
      wsMessageHandler = onMessage;
      onConnect?.();
      return vi.fn();
    });
    const view = render(
      <DisplayBoardUnified
        department="Reg"
        dateStr="2026-05-23"
        boardId="main_board"
        refreshMs={60000}
      />
    );
    // Flush the initial stats fetch inside act context (no act warning).
    await waitFor(() => {
      expect(apiMock.api.get).toHaveBeenCalledWith('/board/state', {
        params: { department: 'Reg', date: '2026-05-23' },
      });
    });
    return { view, push: (msg: unknown) => act(() => { wsMessageHandler!(msg); }) };
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (window.localStorage.getItem as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue(null);
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  });

  it('attaches queue-level owner/specialty/cabinet from queue_update to rows', async () => {
    const { push } = await renderBoard();

    push({
      type: 'queue_update',
      data: {
        doctor_name: 'Synthetic Doctor A',
        specialty: 'cardiology',
        cabinet: '203',
        queue_entries: [
          { number: 7, patient_name: 'Synthetic Patient 1', status: 'waiting', created_at: '2026-05-23T08:00:00' },
        ],
      },
    });

    // Row renders the owner and cabinet that the backend attaches per queue message
    // (the row div prefixes values with an emoji glyph — match by substring).
    expect(await screen.findByText(/Synthetic Doctor A/)).toBeInTheDocument();
    expect(screen.getByText(/203/)).toBeInTheDocument();
  });

  it('renders same numbers from different queues without duplicate React keys', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { push } = await renderBoard();

    // Two queues broadcast to one board: equal ticket numbers, different owners/ids.
    push({
      type: 'initial_state',
      data: {
        queue_entries: [
          { id: 11, number: 7, patient_name: 'Synthetic Patient 1', status: 'waiting', specialist_name: 'Synthetic Doctor A', created_at: '2026-05-23T08:00:00' },
          { id: 12, number: 7, patient_name: 'Synthetic Patient 2', status: 'waiting', specialist_name: 'Synthetic Doctor B', created_at: '2026-05-23T08:01:00' },
        ],
        current_call: null,
        announcements: [],
      },
    });

    expect(await screen.findByText('Synthetic Patient 1')).toBeInTheDocument();
    expect(screen.getByText('Synthetic Patient 2')).toBeInTheDocument();
    // Both owners visible in the rows (distinctness), not only in the current call.
    expect(screen.getByText(/Synthetic Doctor A/)).toBeInTheDocument();
    expect(screen.getByText(/Synthetic Doctor B/)).toBeInTheDocument();

    const dupKeyWarnings = errorSpy.mock.calls
      .map((call) => call.map(String).join(' '))
      .filter((text) => /same key/i.test(text));
    expect(dupKeyWarnings).toEqual([]);
    errorSpy.mockRestore();
  });

  it('resolveBoardEntryKey keeps scope-stable keys and separates equal numbers', () => {
    const base = { number: 7, status: 'waiting' };
    // Same fields → same key (stability across re-renders).
    expect(resolveBoardEntryKey({ ...base, id: 11 }, 0)).toBe(resolveBoardEntryKey({ ...base, id: 11 }, 1));
    // Equal numbers from different scopes → different keys.
    expect(resolveBoardEntryKey({ ...base, id: 11 }, 0)).not.toBe(resolveBoardEntryKey({ ...base, id: 12 }, 0));
    expect(resolveBoardEntryKey({ ...base, doctor_name: 'Synthetic Doctor A', cabinet: '203' }, 0))
      .not.toBe(resolveBoardEntryKey({ ...base, doctor_name: 'Synthetic Doctor B', cabinet: '204' }, 0));
    expect(resolveBoardEntryKey({ ...base, queue_id: 3 }, 0))
      .not.toBe(resolveBoardEntryKey({ ...base, queue_id: 4 }, 0));
    // No scope info at all → deterministic index fallback (no undefined keys).
    expect(resolveBoardEntryKey({ ...base }, 2)).toBe('board-entry-2-7');
  });
});
