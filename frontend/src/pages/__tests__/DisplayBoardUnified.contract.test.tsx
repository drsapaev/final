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

// QR-FE-008: a queue_update payload describes exactly ONE daily queue
// (backend display_websocket broadcasts a per-queue subset to every board).
// The board must merge by the backend-owned queue_id instead of replacing
// the whole read-model — rows of untouched queues must survive a foreign
// queue's update. Synthetic fixtures only.
describe('DisplayBoardUnified queue-scoped merge (QR-FE-008)', () => {
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

  it('queue_update scoped to queue A keeps queue B rows visible', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { push } = await renderBoard();

    // Board-wide snapshot: queue A (queue_id 1) and queue B (queue_id 2),
    // both showing ticket №7 with distinct entry ids and owners.
    push({
      type: 'initial_state',
      data: {
        queue_entries: [
          { id: 11, queue_id: 1, number: 7, patient_name: 'Synthetic Patient A7', status: 'waiting', specialist_name: 'Synthetic Doctor A', created_at: '2026-05-23T08:00:00' },
          { id: 12, queue_id: 2, number: 7, patient_name: 'Synthetic Patient B7', status: 'waiting', specialist_name: 'Synthetic Doctor B', created_at: '2026-05-23T08:01:00' },
        ],
        current_call: null,
        announcements: [],
      },
    });
    expect(await screen.findByText('Synthetic Patient A7')).toBeInTheDocument();
    expect(screen.getByText('Synthetic Patient B7')).toBeInTheDocument();

    // Real-format scoped update: only queue A's subset arrives.
    push({
      type: 'queue_update',
      event_type: 'queue.updated',
      data: {
        queue_id: 1,
        doctor_name: 'Synthetic Doctor A',
        specialty: 'cardiology',
        cabinet: '203',
        queue_entries: [
          { id: 11, queue_id: 1, number: 7, patient_name: 'Synthetic Patient A7-called', status: 'called', called_at: '2026-05-23T08:05:00', created_at: '2026-05-23T08:00:00' },
        ],
        stats: { total: 1, waiting: 0, called: 1, served: 0 },
      },
    });

    // A is updated in place…
    expect(await screen.findByText('Synthetic Patient A7-called')).toBeInTheDocument();
    // …and B survives the foreign queue's update (no cross-queue wipe).
    expect(screen.getByText('Synthetic Patient B7')).toBeInTheDocument();
    expect(screen.getByText(/Synthetic Doctor B/)).toBeInTheDocument();
    // Updated A row keeps its owner identity.
    expect(screen.getByText(/Synthetic Doctor A/)).toBeInTheDocument();

    const dupKeyWarnings = errorSpy.mock.calls
      .map((call) => call.map(String).join(' '))
      .filter((text) => /same key/i.test(text));
    expect(dupKeyWarnings).toEqual([]);
    errorSpy.mockRestore();
  });

  it('scoped update drops completed rows of its queue but keeps other queues', async () => {
    const { push } = await renderBoard();

    push({
      type: 'initial_state',
      data: {
        queue_entries: [
          { id: 21, queue_id: 1, number: 3, patient_name: 'Synthetic Patient A3', status: 'waiting', specialist_name: 'Synthetic Doctor A', created_at: '2026-05-23T08:00:00' },
          { id: 22, queue_id: 2, number: 4, patient_name: 'Synthetic Patient B4', status: 'waiting', specialist_name: 'Synthetic Doctor B', created_at: '2026-05-23T08:01:00' },
        ],
        current_call: null,
        announcements: [],
      },
    });
    expect(await screen.findByText('Synthetic Patient A3')).toBeInTheDocument();

    // Cancellation/no-show semantics: the full per-queue subset (including a
    // completed row) arrives; display read-model mirrors initial_state
    // (waiting/called only), so the finished row leaves the board while the
    // untouched queue stays intact.
    push({
      type: 'queue_update',
      event_type: 'queue.updated',
      data: {
        queue_id: 1,
        doctor_name: 'Synthetic Doctor A',
        queue_entries: [
          { id: 21, queue_id: 1, number: 3, patient_name: 'Synthetic Patient A3', status: 'completed', created_at: '2026-05-23T08:00:00' },
        ],
      },
    });

    await waitFor(() => {
      expect(screen.queryByText('Synthetic Patient A3')).not.toBeInTheDocument();
    });
    expect(screen.getByText('Synthetic Patient B4')).toBeInTheDocument();
  });

  it('queue_update without queue_id falls back to full replace (contract-drift guard)', async () => {
    const { push } = await renderBoard();

    push({
      type: 'initial_state',
      data: {
        queue_entries: [
          { id: 31, queue_id: 1, number: 7, patient_name: 'Synthetic Patient A7', status: 'waiting', specialist_name: 'Synthetic Doctor A', created_at: '2026-05-23T08:00:00' },
          { id: 32, queue_id: 2, number: 8, patient_name: 'Synthetic Patient B8', status: 'waiting', specialist_name: 'Synthetic Doctor B', created_at: '2026-05-23T08:01:00' },
        ],
        current_call: null,
        announcements: [],
      },
    });
    expect(await screen.findByText('Synthetic Patient A7')).toBeInTheDocument();

    // Legacy backend payload without queue_id: previous full-replace
    // behavior is kept deliberately — ownership is never guessed from
    // ticket numbers or specialty labels.
    push({
      type: 'queue_update',
      data: {
        doctor_name: 'Synthetic Doctor A',
        queue_entries: [
          { id: 31, number: 7, patient_name: 'Synthetic Patient A7-v2', status: 'called', created_at: '2026-05-23T08:00:00' },
        ],
      },
    });

    expect(await screen.findByText('Synthetic Patient A7-v2')).toBeInTheDocument();
    expect(screen.queryByText('Synthetic Patient B8')).not.toBeInTheDocument();
  });
});

// QR-FE-009: after a successful WS session drops, the board must present a
// prominent stale-data indicator instead of silently presenting possibly
// outdated rows as live (REST /board/state is stats/settings-only by
// backend contract and never carries patient rows).
describe('DisplayBoardUnified stale-WS banner (QR-FE-009)', () => {
  const renderBoardWithLifecycle = async () => {
    apiMock.api.get.mockResolvedValue({
      data: {
        department: 'Reg',
        date_str: '2026-05-23',
        is_open: true,
        last_ticket: 0,
      },
    });
    let onConnectCb: (() => void) | null = null;
    let onDisconnectCb: (() => void) | null = null;
    wsMock.openDisplayBoardWS.mockImplementation((_boardId: string, _onMessage: (data: unknown) => void, onConnect?: () => void, onDisconnect?: () => void) => {
      onConnectCb = onConnect ?? null;
      onDisconnectCb = onDisconnect ?? null;
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
    await waitFor(() => {
      expect(apiMock.api.get).toHaveBeenCalledWith('/board/state', {
        params: { department: 'Reg', date: '2026-05-23' },
      });
    });
    return {
      view,
      connect: () => act(() => { onConnectCb?.(); }),
      disconnect: () => act(() => { onDisconnectCb?.(); }),
    };
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (window.localStorage.getItem as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue(null);
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  });

  it('shows the stale banner after a dropped WS session and hides it on reconnect', async () => {
    const { connect, disconnect } = await renderBoardWithLifecycle();

    // Initial mount: not connected yet, never connected — no banner.
    expect(screen.queryByTestId('dbu-stale-banner')).not.toBeInTheDocument();

    connect();
    expect(screen.queryByTestId('dbu-stale-banner')).not.toBeInTheDocument();

    disconnect();
    expect(screen.getByTestId('dbu-stale-banner')).toBeInTheDocument();

    // WS reconnects → server initial_state heals the board → banner hides.
    connect();
    expect(screen.queryByTestId('dbu-stale-banner')).not.toBeInTheDocument();
  });
});
