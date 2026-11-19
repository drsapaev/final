import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const wsMock = vi.hoisted(() => ({ openDisplayBoardWS: vi.fn() }));
const apiMock = vi.hoisted(() => ({ api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
const tokenManagerMock = vi.hoisted(() => ({ getAccessToken: vi.fn((): string | null => null) }));

vi.mock('../../api/client', () => apiMock);
vi.mock('../../api/ws', () => wsMock);
vi.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ theme: 'light' }) }));
vi.mock('../../utils/logger', () => ({
  default: { log: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../utils/tokenManager', () => ({ tokenManager: tokenManagerMock }));

import DisplayBoardUnified from '../DisplayBoardUnified';

const DEVICE_SECRET = 'synthetic-device-secret-value-0123456789abcdef';

function openPublicBoard(query = '?board=main_board') {
  window.history.replaceState(null, '', `/display-board${query}`);
}

describe('DisplayBoardUnified public device provisioning', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    openPublicBoard();
    tokenManagerMock.getAccessToken.mockReturnValue(null);
    apiMock.api.get.mockResolvedValue({ data: { department: 'Reg', date_str: 'synthetic' } });
    apiMock.api.post.mockRejectedValue({ response: { status: 401 } });
    apiMock.api.delete.mockResolvedValue({ status: 204 });
    wsMock.openDisplayBoardWS.mockImplementation((...args: unknown[]) => {
      const tokenProvider = args[4];
      if (typeof tokenProvider === 'function') {
        void (tokenProvider as () => Promise<string | null>)().catch(() => undefined);
      }
      return vi.fn();
    });
  });

  it('shows a provisioning form instead of opening an unauthenticated board socket', async () => {
    render(<DisplayBoardUnified department="Reg" dateStr="synthetic" boardId="main_board" />);

    expect(await screen.findByTestId('display-device-provisioning')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Табло не настроено' })).toBeInTheDocument();
    expect(wsMock.openDisplayBoardWS).toHaveBeenCalledTimes(1);
    const [, , , , tokenProvider] = wsMock.openDisplayBoardWS.mock.calls[0];
    expect(typeof tokenProvider).toBe('function');
    await expect(tokenProvider()).rejects.toMatchObject({
      code: 'DISPLAY_DEVICE_PROVISIONING_REQUIRED',
    });
  });

  it('exchanges the one-time code for an HttpOnly session without persisting the secret', async () => {
    const user = userEvent.setup();
    render(<DisplayBoardUnified department="Reg" dateStr="synthetic" boardId="main_board" />);
    await screen.findByTestId('display-device-provisioning');
    apiMock.api.post.mockResolvedValueOnce({
      data: {
        access_token: 'synthetic-device-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        board_name: 'main_board',
      },
    }).mockResolvedValueOnce({
      data: {
        access_token: 'synthetic-session-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        board_name: 'main_board',
      },
    });

    await user.type(screen.getByLabelText('ID устройства'), '17');
    await user.type(screen.getByLabelText('Код устройства'), DEVICE_SECRET);
    await user.click(screen.getByRole('button', { name: 'Подключить табло' }));

    await waitFor(() => expect(wsMock.openDisplayBoardWS).toHaveBeenCalledTimes(2));
    expect(apiMock.api.post).toHaveBeenCalledWith('/display/devices/token', {
      board_name: 'main_board',
    }, { withCredentials: true });
    expect(apiMock.api.post).toHaveBeenCalledWith('/display/devices/token', {
      board_name: 'main_board',
      device_id: 17,
      secret: DEVICE_SECRET,
    }, { withCredentials: true });
    const storedValues = Array.from({ length: window.localStorage.length }, (_, index) => {
      const key = window.localStorage.key(index);
      return key ? window.localStorage.getItem(key) : null;
    }).join('\n');
    expect(storedValues).not.toContain(DEVICE_SECRET);

    const [, , , , tokenProvider] = wsMock.openDisplayBoardWS.mock.calls[0];
    expect(typeof tokenProvider).toBe('function');
    apiMock.api.post.mockResolvedValueOnce({
      data: {
        access_token: 'synthetic-refreshed-device-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        board_name: 'main_board',
      },
    });
    await expect(tokenProvider()).resolves.toBe('synthetic-refreshed-device-jwt');
    expect(apiMock.api.post).toHaveBeenLastCalledWith('/display/devices/token', {
      board_name: 'main_board',
    }, { withCredentials: true });
  });

  it('forgets only the selected board session from the URL control', async () => {
    openPublicBoard('?board=main_board&forget-device=1');

    render(<DisplayBoardUnified department="Reg" dateStr="synthetic" boardId="main_board" />);

    expect(await screen.findByTestId('display-device-provisioning')).toBeInTheDocument();
    expect(apiMock.api.delete).toHaveBeenCalledWith('/display/devices/token', {
      params: { board_name: 'main_board' },
      withCredentials: true,
    });
    expect(window.location.search).toBe('?board=main_board');
  });

  it('keeps a wrong-board credential out of storage and shows setup again', async () => {
    const user = userEvent.setup();
    render(<DisplayBoardUnified department="Reg" dateStr="synthetic" boardId="main_board" />);
    await screen.findByTestId('display-device-provisioning');
    apiMock.api.post.mockResolvedValueOnce({
      data: {
        access_token: 'synthetic-device-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        board_name: 'another_board',
      },
    });

    await user.type(screen.getByLabelText('ID устройства'), '17');
    await user.type(screen.getByLabelText('Код устройства'), DEVICE_SECRET);
    await user.click(screen.getByRole('button', { name: 'Подключить табло' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Не удалось подтвердить устройство.',
    );
    expect(wsMock.openDisplayBoardWS).toHaveBeenCalledTimes(1);
  });
});
