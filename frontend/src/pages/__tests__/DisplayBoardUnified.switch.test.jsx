import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiGet, fetchBoardDisplayStateV1, openDisplayBoardWS } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  fetchBoardDisplayStateV1: vi.fn(),
  openDisplayBoardWS: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  api: {
    get: apiGet,
  },
}));

vi.mock('../../api/boardDisplay', () => ({
  fetchBoardDisplayStateV1,
}));

vi.mock('../../api/ws', () => ({
  openDisplayBoardWS,
}));

vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: vi.fn(),
}));

vi.mock('../../utils/logger', () => ({
  default: {
    log: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

import DisplayBoardUnified from '../DisplayBoardUnified.jsx';

function createWsCloser() {
  const close = vi.fn();
  close.close = close;
  return close;
}

describe('DisplayBoardUnified metadata source switch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    openDisplayBoardWS.mockReturnValue(createWsCloser());
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue();
  });

  it('uses the new adapter for clean metadata fields while keeping legacy compatibility fallback', async () => {
    fetchBoardDisplayStateV1.mockResolvedValue({
      boardKey: 'main_board',
      brand: 'Adapter Brand',
      logo: '/static/adapter-logo.png',
      announcement: 'Adapter announcement',
      announcement_ru: 'Адаптер RU',
      announcement_uz: 'Adapter UZ',
      announcement_en: 'Adapter EN',
      primary_color: '#111111',
      bg_color: '#fafafa',
      text_color: '#222222',
      contrast_default: false,
      kiosk_default: true,
      sound_default: false,
    });

    apiGet.mockImplementation((url) => {
      if (url === '/queues/stats') {
        return Promise.resolve({
          last_ticket: 12,
          waiting: 4,
          serving: 1,
          done: 7,
        });
      }
      if (url === '/board/state') {
        return Promise.resolve({
          brand: 'Legacy Brand',
          logo: '/static/legacy-logo.png',
          is_paused: true,
          is_closed: false,
          announcement: 'Legacy announcement',
          contrast_default: true,
          kiosk_default: false,
          sound_default: true,
        });
      }
      if (url === '/queue/queue/status') {
        return Promise.resolve([]);
      }
      return Promise.resolve({});
    });

    render(<DisplayBoardUnified refreshMs={60000} />);

    await waitFor(() => {
      expect(fetchBoardDisplayStateV1).toHaveBeenCalledWith('main_board');
    });

    expect(await screen.findByText('Adapter Brand')).toBeInTheDocument();
    expect(screen.getByText('Адаптер RU')).toBeInTheDocument();
    expect(screen.getByText('Работа приостановлена')).toBeInTheDocument();
    expect(screen.getByAltText('Adapter Brand')).toHaveAttribute(
      'src',
      '/static/adapter-logo.png'
    );
    expect(screen.queryByText('Legacy Brand')).not.toBeInTheDocument();
    expect(screen.queryByText('Legacy announcement')).not.toBeInTheDocument();
    expect(screen.getByTitle('Включить звук')).toBeInTheDocument();

    expect(apiGet.mock.calls.some(([url]) => url === '/queues/stats')).toBe(true);
    expect(apiGet.mock.calls.some(([url]) => url === '/board/state')).toBe(true);
    expect(openDisplayBoardWS).toHaveBeenCalledWith(
      'main_board',
      expect.any(Function),
      expect.any(Function),
      expect.any(Function)
    );
  });

  it('falls back to legacy board metadata when the new adapter is unavailable', async () => {
    fetchBoardDisplayStateV1.mockRejectedValue(new Error('adapter unavailable'));

    apiGet.mockImplementation((url) => {
      if (url === '/queues/stats') {
        return Promise.resolve({
          last_ticket: 2,
          waiting: 1,
          serving: 0,
          done: 0,
        });
      }
      if (url === '/board/state') {
        return Promise.resolve({
          brand: 'Legacy Only Board',
          announcement: 'Legacy only announcement',
          logo: '/static/legacy-only.png',
          is_closed: true,
          sound_default: true,
        });
      }
      if (url === '/queue/queue/status') {
        return Promise.resolve([]);
      }
      return Promise.resolve({});
    });

    render(<DisplayBoardUnified refreshMs={60000} />);

    expect(await screen.findByText('Legacy Only Board')).toBeInTheDocument();
    expect(screen.getByText('Legacy only announcement')).toBeInTheDocument();
    expect(screen.getByText('Клиника закрыта')).toBeInTheDocument();
    expect(screen.getByAltText('Legacy Only Board')).toHaveAttribute(
      'src',
      '/static/legacy-only.png'
    );
  });
});
