import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.jsx';

const { apiGet, apiPost, apiDelete, loggerInfo, loggerError } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
  loggerInfo: vi.fn(),
  loggerError: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: apiGet,
    post: apiPost,
    delete: apiDelete,
  },
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    info: loggerInfo,
    error: loggerError,
  },
}));

import TwoFactorManager from '../TwoFactorManager.jsx';

function apiResponse(data) {
  return Promise.resolve({ data });
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
    apiGet.mockImplementation((url) => {
      const path = String(url);

      if (path === '/2fa/status') {
        return apiResponse({
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

      if (path === '/2fa/devices') {
        return apiResponse({ devices: [] });
      }

      if (path === '/2fa/security-logs') {
        return apiResponse({ logs: [] });
      }

      if (path === '/2fa/recovery-methods') {
        return apiResponse({ methods: [] });
      }

      throw new Error(`Unhandled api.get: ${path}`);
    });

    apiPost.mockImplementation((url) => {
      const path = String(url);
      throw new Error(`Unhandled api.post: ${path}`);
    });

    apiDelete.mockImplementation((url) => {
      const path = String(url);
      throw new Error(`Unhandled api.delete: ${path}`);
    });
  });

  it('does not expose backup-code regeneration before 2FA is enabled', async () => {
    renderManager();

    expect(await screen.findByText(/Резервные коды пока недоступны/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /создать новый комплект/i })).not.toBeInTheDocument();
    expect(
      apiPost.mock.calls.some(([url]) => String(url).includes('/2fa/backup-codes/regenerate'))
    ).toBe(false);
  });

  it('verifies setup before allowing backup code regeneration', async () => {
    let statusCalls = 0;

    apiGet.mockImplementation((url) => {
      const path = String(url);

      if (path === '/2fa/status') {
        statusCalls += 1;
        return apiResponse(
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

      if (path === '/2fa/devices') {
        return apiResponse({ devices: [] });
      }

      if (path === '/2fa/security-logs') {
        return apiResponse({ logs: [] });
      }

      if (path === '/2fa/recovery-methods') {
        return apiResponse({ methods: [] });
      }

      throw new Error(`Unhandled api.get: ${path}`);
    });

    apiPost.mockImplementation((url, body, config) => {
      const path = String(url);

      if (path === '/2fa/setup') {
        return apiResponse({
          qr_code_url: 'data:image/png;base64,abc',
          secret_key: 'SECRETKEY123',
          backup_codes: ['AAAA1111', 'BBBB2222'],
          recovery_token: null,
          expires_at: null,
        });
      }

      if (path === '/2fa/verify-setup' && config?.params?.totp_code === '123456') {
        return apiResponse({
          success: true,
          message: 'TOTP setup verified successfully',
        });
      }

      if (path === '/2fa/backup-codes/regenerate') {
        return apiResponse({
          backup_codes: ['CCCC3333', 'DDDD4444'],
        });
      }

      throw new Error(`Unhandled api.post: ${path}`);
    });

    renderManager();

    fireEvent.click(await screen.findByRole('button', { name: /Включить 2FA/i }));

    expect(await screen.findByText(/Подтверждение настройки 2FA/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Введите 6-значный код'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Подтвердить и включить 2FA/i }));

    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        '/2fa/verify-setup',
        null,
        expect.objectContaining({
          params: { totp_code: '123456' },
        })
      );
    });

    expect(await screen.findByText('AAAA1111')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /Создать новый комплект/i })[0]);
    fireEvent.click(await screen.findByRole('button', { name: /Подтвердить обновление кодов/i }));

    expect(await screen.findByText('CCCC3333')).toBeInTheDocument();
    expect(apiPost).toHaveBeenCalledWith('/2fa/backup-codes/regenerate');
  });

  it('revokes trusted devices through the supported delete endpoint', async () => {
    apiGet.mockImplementation((url) => {
      const path = String(url);

      if (path === '/2fa/status') {
        return apiResponse({
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

      if (path === '/2fa/devices') {
        return apiResponse({
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

      if (path === '/2fa/security-logs') {
        return apiResponse({ logs: [] });
      }

      if (path === '/2fa/recovery-methods') {
        return apiResponse({ methods: [] });
      }

      throw new Error(`Unhandled api.get: ${path}`);
    });

    apiDelete.mockImplementation((url) => {
      const path = String(url);

      if (path === '/2fa/devices/7') {
        return apiResponse({ success: true, message: 'Device untrusted successfully' });
      }

      throw new Error(`Unhandled api.delete: ${path}`);
    });

    renderManager();

    expect(await screen.findByText('Clinic Desktop')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Отозвать доступ/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Подтвердить отзыв/i }));

    await waitFor(() => {
      expect(apiDelete).toHaveBeenCalledWith('/2fa/devices/7');
    });
  });
});
