// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

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

import DisplayBoardUnified from '../DisplayBoardUnified';

describe('DisplayBoardUnified contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.getItem.mockReturnValue(null);
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  });

  it('treats /board/state as stats-only and uses websocket initial_state for live rows', async () => {
    let wsMessageHandler;
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
      wsMessageHandler({
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
