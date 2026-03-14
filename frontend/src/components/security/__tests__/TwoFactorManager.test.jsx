import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.jsx';

import { tokenManager } from '../../../utils/tokenManager';

const { loggerInfo, loggerError, loggerWarn, loggerLog } = vi.hoisted(() => ({
  loggerInfo: vi.fn(),
  loggerError: vi.fn(),
  loggerWarn: vi.fn(),
  loggerLog: vi.fn(),
}));

const { getAccessToken, getRefreshToken, clearAll, setAccessToken } = vi.hoisted(() => ({
  getAccessToken: vi.fn(() => 'test-token'),
  getRefreshToken: vi.fn(() => 'test-refresh-token'),
  clearAll: vi.fn(),
  setAccessToken: vi.fn(),
}));

vi.mock('../../../utils/tokenManager', () => {
  const m = {
    getAccessToken,
    getRefreshToken,
    clearAll,
    setAccessToken,
  };
  return {
    tokenManager: m,
    default: m
  };
});

vi.mock('../../../api/client', () => {
  return {
    api: {
      get: vi.fn(async (url) => {
        const res = await global.fetch(url.startsWith('/api') ? url : `/api/v1${url}`, { method: 'GET' });
        const data = await res.json();
        return { data };
      }),
      post: vi.fn(async (url, data, config) => {
        let fullUrl = url.startsWith('/api') ? url : `/api/v1${url}`;
        if (config?.params?.totp_code) {
          fullUrl += `?totp_code=${config.params.totp_code}`;
        }
        const res = await global.fetch(fullUrl, { method: 'POST', body: JSON.stringify(data) });
        const resData = await res.json();
        return { data: resData };
      }),
      delete: vi.fn(async (url) => {
        const res = await global.fetch(url.startsWith('/api') ? url : `/api/v1${url}`, { method: 'DELETE' });
        const data = await res.json();
        return { data };
      }),
      defaults: { headers: { common: {} } },
      interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
    }
  };
});

vi.mock('../../../utils/logger', () => {
  return {
    default: {
      info: loggerInfo,
      error: loggerError,
      log: loggerLog,
      warn: loggerWarn,
    }
  };
});

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
    global.fetch = vi.fn((input, init) => {
      const url = String(input);

      if (url.endsWith('/api/v1/2fa/status')) {
        return jsonResponse({
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

      if (url.endsWith('/api/v1/2fa/devices')) {
        return jsonResponse({ devices: [] });
      }

      if (url.endsWith('/api/v1/2fa/security-logs')) {
        return jsonResponse({ logs: [] });
      }

      if (url.endsWith('/api/v1/2fa/recovery-methods')) {
        return jsonResponse({ methods: [] });
      }

      throw new Error(`Unhandled fetch: ${url} ${(init?.method || 'GET')}`);
    });
  });

  it('does not expose backup-code regeneration before 2FA is enabled', async () => {
    renderManager();

    expect(await screen.findByText(/Резервные коды пока недоступны/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /создать новый комплект/i })).not.toBeInTheDocument();
    expect(
      global.fetch.mock.calls.some(([url]) => String(url).includes('/api/v1/2fa/backup-codes/regenerate'))
    ).toBe(false);
  });

  it('verifies setup before allowing backup code regeneration', async () => {
    let statusCalls = 0;

    global.fetch = vi.fn((input, init) => {
      const url = String(input);
      const method = init?.method || 'GET';

      if (url.endsWith('/api/v1/2fa/status')) {
        statusCalls += 1;
        return jsonResponse(
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

      if (url.endsWith('/api/v1/2fa/devices')) {
        return jsonResponse({ devices: [] });
      }

      if (url.endsWith('/api/v1/2fa/security-logs')) {
        return jsonResponse({ logs: [] });
      }

      if (url.endsWith('/api/v1/2fa/recovery-methods')) {
        return jsonResponse({ methods: [] });
      }

      if (url.endsWith('/api/v1/2fa/setup') && method === 'POST') {
        return jsonResponse({
          qr_code_url: 'data:image/png;base64,abc',
          secret_key: 'SECRETKEY123',
          backup_codes: ['AAAA1111', 'BBBB2222'],
          recovery_token: null,
          expires_at: null,
        });
      }

      if (url.includes('/api/v1/2fa/verify-setup?totp_code=123456') && method === 'POST') {
        return jsonResponse({
          success: true,
          message: 'TOTP setup verified successfully',
        });
      }

      if (url.endsWith('/api/v1/2fa/backup-codes/regenerate') && method === 'POST') {
        return jsonResponse({
          backup_codes: ['CCCC3333', 'DDDD4444'],
        });
      }

      throw new Error(`Unhandled fetch: ${url} ${method}`);
    });

    renderManager();

    fireEvent.click(await screen.findByRole('button', { name: /Включить 2FA/i }));

    expect(await screen.findByText(/Подтверждение настройки 2FA/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Введите 6-значный код'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Подтвердить и включить 2FA/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/2fa/verify-setup?totp_code=123456'),
        expect.objectContaining({ method: 'POST' })
      );
    });

    expect(await screen.findByText('AAAA1111')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /Создать новый комплект/i })[0]);
    fireEvent.click(await screen.findByRole('button', { name: /Подтвердить обновление кодов/i }));

    expect(await screen.findByText('CCCC3333')).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/2fa/backup-codes/regenerate',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('revokes trusted devices through the supported delete endpoint', async () => {
    global.fetch = vi.fn((input, init) => {
      const url = String(input);
      const method = init?.method || 'GET';

      if (url.endsWith('/api/v1/2fa/status')) {
        return jsonResponse({
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

      if (url.endsWith('/api/v1/2fa/devices') && method === 'GET') {
        return jsonResponse({
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

      if (url.endsWith('/api/v1/2fa/security-logs')) {
        return jsonResponse({ logs: [] });
      }

      if (url.endsWith('/api/v1/2fa/recovery-methods')) {
        return jsonResponse({ methods: [] });
      }

      if (url.endsWith('/api/v1/2fa/devices/7') && method === 'DELETE') {
        return jsonResponse({ success: true, message: 'Device untrusted successfully' });
      }

      throw new Error(`Unhandled fetch: ${url} ${method}`);
    });

    renderManager();

    expect(await screen.findByText('Clinic Desktop')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Отозвать доступ/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Подтвердить отзыв/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/2fa/devices/7',
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });
});
