import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const wsMock = vi.hoisted(() => ({ openDisplayBoardWS: vi.fn() }));
const apiMock = vi.hoisted(() => ({ api: { get: vi.fn(), post: vi.fn() } }));
const tokenManagerMock = vi.hoisted(() => ({ getAccessToken: vi.fn((): string | null => null) }));

vi.mock('../../api/client', () => apiMock);
vi.mock('../../api/ws', () => wsMock);
vi.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ theme: 'light' }) }));
vi.mock('../../utils/logger', () => ({
  default: { log: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../utils/tokenManager', () => ({ tokenManager: tokenManagerMock }));

import DisplayBoardUnified from '../DisplayBoardUnified';
import { readDisplayDeviceCredential, saveDisplayDeviceCredential } from '../../api/displayDeviceAuth';

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
    apiMock.api.post.mockResolvedValue({
      data: {
        access_token: 'synthetic-device-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        board_name: 'main_board',
      },
    });
    wsMock.openDisplayBoardWS.mockReturnValue(vi.fn());
  });

  it('shows a provisioning form instead of opening an unauthenticated board socket', async () => {
    render(<DisplayBoardUnified department="Reg" dateStr="synthetic" boardId="main_board" />);

    expect(await screen.findByTestId('display-device-provisioning')).toBeInTheDocument();
    expect(screen.getByText(/Табло не настроено/)).toBeInTheDocument();
    expect(wsMock.openDisplayBoardWS).not.toHaveBeenCalled();
  });

  it('validates and stores the one-time credential, then uses a refreshable token provider', async () => {
    const user = userEvent.setup();
    render(<DisplayBoardUnified department="Reg" dateStr="synthetic" boardId="main_board" />);

    await user.type(screen.getByLabelText('ID устройства'), '17');
    await user.type(screen.getByLabelText('Код устройства'), DEVICE_SECRET);
    await user.click(screen.getByRole('button', { name: 'Подключить табло' }));

    await waitFor(() => expect(wsMock.openDisplayBoardWS).toHaveBeenCalledTimes(1));
    expect(apiMock.api.post).toHaveBeenCalledWith('/display/devices/token', {
      device_id: 17,
      secret: DEVICE_SECRET,
    });
    expect(readDisplayDeviceCredential('main_board')).toEqual({
      deviceId: 17,
      secret: DEVICE_SECRET,
    });

    const [, , , , tokenProvider] = wsMock.openDisplayBoardWS.mock.calls[0];
    expect(typeof tokenProvider).toBe('function');
    tokenManagerMock.getAccessToken.mockReturnValue('synthetic-staff-jwt');
    await expect(tokenProvider()).resolves.toBe('synthetic-staff-jwt');
    expect(apiMock.api.post).toHaveBeenCalledTimes(1);
  });

  it('forgets only the selected board credential from the URL control', async () => {
    saveDisplayDeviceCredential('main_board', { deviceId: 17, secret: DEVICE_SECRET });
    saveDisplayDeviceCredential('other_board', { deviceId: 22, secret: DEVICE_SECRET });
    openPublicBoard('?board=main_board&forget-device=1');

    render(<DisplayBoardUnified department="Reg" dateStr="synthetic" boardId="main_board" />);

    expect(await screen.findByTestId('display-device-provisioning')).toBeInTheDocument();
    expect(readDisplayDeviceCredential('main_board')).toBeNull();
    expect(readDisplayDeviceCredential('other_board')).not.toBeNull();
    expect(window.location.search).toBe('?board=main_board');
  });

  it('keeps a wrong-board credential out of storage and shows setup again', async () => {
    const user = userEvent.setup();
    apiMock.api.post.mockResolvedValueOnce({
      data: {
        access_token: 'synthetic-device-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        board_name: 'another_board',
      },
    });
    render(<DisplayBoardUnified department="Reg" dateStr="synthetic" boardId="main_board" />);

    await user.type(screen.getByLabelText('ID устройства'), '17');
    await user.type(screen.getByLabelText('Код устройства'), DEVICE_SECRET);
    await user.click(screen.getByRole('button', { name: 'Подключить табло' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Не удалось подтвердить устройство.',
    );
    expect(readDisplayDeviceCredential('main_board')).toBeNull();
    expect(wsMock.openDisplayBoardWS).not.toHaveBeenCalled();
  });
});
