import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.jsx';

const { getAccessToken, loggerInfo, loggerError, mockApiGet, mockApiPost, mockApiDelete } = vi.hoisted(() => ({
  getAccessToken: vi.fn(() => 'test-token'),
  loggerInfo: vi.fn(),
  loggerError: vi.fn(),
  mockApiGet: vi.fn(),
  mockApiPost: vi.fn(),
  mockApiDelete: vi.fn(),
}));

vi.mock('../../../utils/tokenManager', () => {
  const getAccessToken = vi.fn(() => 'test-token');
  const getRefreshToken = vi.fn(() => null);
  const setAccessToken = vi.fn();
  const clearAll = vi.fn();

  return {
    __esModule: true,
    tokenManager: {
      getAccessToken,
      getRefreshToken,
      setAccessToken,
      clearAll,
    },
    default: {
      getAccessToken,
      getRefreshToken,
      setAccessToken,
      clearAll,
    }
  };
});

vi.mock('../../../api/client', () => {
  return {
    api: {
      get: mockApiGet,
      post: mockApiPost,
      delete: mockApiDelete,
      defaults: { headers: { common: {} } },
      interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } }
    },
  };
});

vi.mock('../../../utils/logger', () => ({
  default: {
    info: loggerInfo,
    error: loggerError,
  },
}));

import TwoFactorManager from '../TwoFactorManager.jsx';

function jsonResponse(data, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: async () => data,
  });
}

function renderManager() {
  return render(
    <MacOSThemeProvider>
      <ThemeProvider>
        <TwoFactorManager />
      </ThemeProvider>
    </MacOSThemeProvider>
  );
}

describe('TwoFactorManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockApiGet.mockImplementation((url) => {
      if (url.endsWith('/2fa/status')) {
        return Promise.resolve({ data: {
          enabled: false,
          totp_enabled: false,
          totp_verified: false,
          backup_codes_generated: false,
          backup_codes_count: 0,
          recovery_enabled: false,
          recovery_email: null,
          recovery_phone: null,
          trusted_devices_count: 0,
          last_used: null,
        } });
      }

      if (url.endsWith('/2fa/devices')) {
        return Promise.resolve({ data: { devices: [] } });
      }

      if (url.endsWith('/2fa/security-logs')) {
        return Promise.resolve({ data: { logs: [] } });
      }

      if (url.endsWith('/2fa/recovery-methods')) {
        return Promise.resolve({ data: { methods: [] } });
      }

      return Promise.resolve({ data: {} });
    });

    mockApiPost.mockImplementation(() => Promise.resolve({ data: {} }));
    mockApiDelete.mockImplementation(() => Promise.resolve({ data: {} }));
  });

  it('does not expose backup-code regeneration before 2FA is enabled', async () => {
    renderManager();

    expect(await screen.findByText(/Резервные коды пока недоступны/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /создать новый комплект/i })).not.toBeInTheDocument();
    expect(
      mockApiPost.mock.calls.some(([url]) => String(url).includes('/2fa/backup-codes/regenerate'))
    ).toBe(false);
  });

  it('verifies setup before allowing backup code regeneration', async () => {
    let statusCalls = 0;

    mockApiGet.mockImplementation((url) => {
      if (url.endsWith('/2fa/status')) {
        statusCalls += 1;
        return Promise.resolve({ data:
          statusCalls === 1
            ? {
              enabled: false,
              totp_enabled: false,
              totp_verified: false,
              backup_codes_generated: false,
              backup_codes_count: 0,
              recovery_enabled: false,
              recovery_email: null,
              recovery_phone: null,
              trusted_devices_count: 0,
              last_used: null,
            }
            : {
              enabled: true,
              totp_enabled: true,
              totp_verified: true,
              backup_codes_generated: true,
              backup_codes_count: 10,
              recovery_enabled: false,
              recovery_email: null,
              recovery_phone: null,
              trusted_devices_count: 0,
              last_used: null,
            }
        });
      }

      if (url.endsWith('/2fa/devices')) {
        return Promise.resolve({ data: { devices: [] } });
      }

      if (url.endsWith('/2fa/security-logs')) {
        return Promise.resolve({ data: { logs: [] } });
      }

      if (url.endsWith('/2fa/recovery-methods')) {
        return Promise.resolve({ data: { methods: [] } });
      }

      return Promise.resolve({ data: {} });
    });

    mockApiPost.mockImplementation((url) => {
      if (url.endsWith('/2fa/setup')) {
        return Promise.resolve({ data: {
          qr_code_url: 'data:image/png;base64,abc',
          secret_key: 'SECRETKEY123',
          backup_codes: ['AAAA1111', 'BBBB2222'],
          recovery_token: null,
          expires_at: null,
        } });
      }

      if (url.includes('/2fa/verify-setup')) {
        return Promise.resolve({ data: {
          success: true,
          message: 'TOTP setup verified successfully',
        } });
      }

      if (url.endsWith('/2fa/backup-codes/regenerate')) {
        return Promise.resolve({ data: {
          backup_codes: ['CCCC3333', 'DDDD4444'],
        } });
      }

      return Promise.resolve({ data: {} });
    });

    renderManager();

    fireEvent.click(await screen.findByRole('button', { name: /Включить 2FA/i }));

    expect(await screen.findByText(/Подтверждение настройки 2FA/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Введите 6-значный код'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Подтвердить и включить 2FA/i }));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        expect.stringContaining('/2fa/verify-setup'),
        null,
        expect.objectContaining({ params: { totp_code: '123456' } })
      );
    });

    expect(await screen.findByText('AAAA1111')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /Создать новый комплект/i })[0]);
    fireEvent.click(await screen.findByRole('button', { name: /Подтвердить обновление кодов/i }));

    expect(await screen.findByText('CCCC3333')).toBeInTheDocument();
    expect(mockApiPost).toHaveBeenCalledWith(
      '/2fa/backup-codes/regenerate'
    );
  });

  it('revokes trusted devices through the supported delete endpoint', async () => {
    mockApiGet.mockImplementation((url) => {
      if (url.endsWith('/2fa/status')) {
        return Promise.resolve({ data: {
          enabled: true,
          totp_enabled: true,
          totp_verified: true,
          backup_codes_generated: true,
          backup_codes_count: 10,
          recovery_enabled: false,
          recovery_email: null,
          recovery_phone: null,
          trusted_devices_count: 1,
          last_used: '2026-03-03T10:00:00Z',
        } });
      }

      if (url.endsWith('/2fa/devices')) {
        return Promise.resolve({ data: {
          devices: [
            {
              id: 7,
              device_name: 'Clinic Desktop',
              device_type: 'desktop',
              trusted: true,
              active: true,
              ip_address: '127.0.0.1',
              user_agent: 'Chrome',
              last_used: '2026-03-03T10:00:00Z',
            },
          ],
        } });
      }

      if (url.endsWith('/2fa/security-logs')) {
        return Promise.resolve({ data: { logs: [] } });
      }

      if (url.endsWith('/2fa/recovery-methods')) {
        return Promise.resolve({ data: { methods: [] } });
      }

      return Promise.resolve({ data: {} });
    });

    mockApiDelete.mockImplementation((url) => {
      if (url.endsWith('/2fa/devices/7')) {
        return Promise.resolve({ data: { success: true, message: 'Device untrusted successfully' } });
      }
      return Promise.resolve({ data: {} });
    });

    renderManager();

    expect(await screen.findByText('Clinic Desktop')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Отозвать доступ/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Подтвердить отзыв/i }));

    await waitFor(() => {
      expect(mockApiDelete).toHaveBeenCalledWith(
        '/2fa/devices/7'
      );
    });
  });
});
