import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.jsx';
import { api } from '../../../api/client';

const { getAccessToken, loggerInfo, loggerError } = vi.hoisted(() => ({
  getAccessToken: vi.fn(() => 'test-token'),
  loggerInfo: vi.fn(),
  loggerError: vi.fn(),
}));

vi.mock('../../../utils/tokenManager', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    default: {
      ...actual.default,
      getAccessToken,
    },
    tokenManager: {
      ...actual.tokenManager,
      getAccessToken,
    },
  };
});

vi.mock('../../../utils/logger', () => ({
  default: {
    info: loggerInfo,
    error: loggerError,
  },
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  }
}));

import TwoFactorManager from '../TwoFactorManager.jsx';

function axiosResponse(data, status = 200) {
  return Promise.resolve({
    data,
    status,
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

    api.get.mockImplementation((url) => {
      if (url.endsWith('/2fa/status')) {
        return axiosResponse({
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
        });
      }
      if (url.endsWith('/2fa/devices')) {
        return axiosResponse({ devices: [] });
      }
      if (url.endsWith('/2fa/security-logs')) {
        return axiosResponse({ logs: [] });
      }
      if (url.endsWith('/2fa/recovery-methods')) {
        return axiosResponse({ methods: [] });
      }
      return Promise.reject(new Error(`Unhandled get: ${url}`));
    });

    api.post.mockImplementation((url) => Promise.reject(new Error(`Unhandled post: ${url}`)));
    api.delete.mockImplementation((url) => Promise.reject(new Error(`Unhandled delete: ${url}`)));
  });

  it('does not expose backup-code regeneration before 2FA is enabled', async () => {
    renderManager();

    expect(await screen.findByText(/Резервные коды пока недоступны/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /создать новый комплект/i })).not.toBeInTheDocument();
    expect(
      api.post.mock.calls.some(([url]) => url.includes('/2fa/backup-codes/regenerate'))
    ).toBe(false);
  });

  it('verifies setup before allowing backup code regeneration', async () => {
    let statusCalls = 0;

    api.get.mockImplementation((url) => {
      if (url.endsWith('/2fa/status')) {
        statusCalls += 1;
        return axiosResponse(
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
        );
      }
      if (url.endsWith('/2fa/devices')) return axiosResponse({ devices: [] });
      if (url.endsWith('/2fa/security-logs')) return axiosResponse({ logs: [] });
      if (url.endsWith('/2fa/recovery-methods')) return axiosResponse({ methods: [] });
      return Promise.reject(new Error(`Unhandled get: ${url}`));
    });

    api.post.mockImplementation((url, data, config) => {
      if (url.endsWith('/2fa/setup')) {
        return axiosResponse({
          qr_code_url: 'data:image/png;base64,abc',
          secret_key: 'SECRETKEY123',
          backup_codes: ['AAAA1111', 'BBBB2222'],
          recovery_token: null,
          expires_at: null,
        });
      }
      if (url.includes('/2fa/verify-setup')) {
        return axiosResponse({
          success: true,
          message: 'TOTP setup verified successfully',
        });
      }
      if (url.endsWith('/2fa/backup-codes/regenerate')) {
        return axiosResponse({
          backup_codes: ['CCCC3333', 'DDDD4444'],
        });
      }
      return Promise.reject(new Error(`Unhandled post: ${url}`));
    });

    renderManager();

    fireEvent.click(await screen.findByRole('button', { name: /Включить 2FA/i }));

    expect(await screen.findByText(/Подтверждение настройки 2FA/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Введите 6-значный код'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Подтвердить и включить 2FA/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        expect.stringContaining('/2fa/verify-setup'),
        null,
        expect.objectContaining({ params: { totp_code: '123456' } })
      );
    });

    expect(await screen.findByText('AAAA1111')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /Создать новый комплект/i })[0]);
    fireEvent.click(await screen.findByRole('button', { name: /Подтвердить обновление кодов/i }));

    expect(await screen.findByText('CCCC3333')).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith('/2fa/backup-codes/regenerate');
  });

  it('revokes trusted devices through the supported delete endpoint', async () => {
    api.get.mockImplementation((url) => {
      if (url.endsWith('/2fa/status')) {
        return axiosResponse({
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
        });
      }
      if (url.endsWith('/2fa/devices')) {
        return axiosResponse({
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
        });
      }
      if (url.endsWith('/2fa/security-logs')) return axiosResponse({ logs: [] });
      if (url.endsWith('/2fa/recovery-methods')) return axiosResponse({ methods: [] });
      return Promise.reject(new Error(`Unhandled get: ${url}`));
    });

    api.delete.mockImplementation((url) => {
      if (url.endsWith('/2fa/devices/7')) {
        return axiosResponse({ success: true, message: 'Device untrusted successfully' });
      }
      return Promise.reject(new Error(`Unhandled delete: ${url}`));
    });

    renderManager();

    expect(await screen.findByText('Clinic Desktop')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Отозвать доступ/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Подтвердить отзыв/i }));

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith('/2fa/devices/7');
    });
  });
});
