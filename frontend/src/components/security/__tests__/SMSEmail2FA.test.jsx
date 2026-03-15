import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';

const { getAccessToken } = vi.hoisted(() => ({
  getAccessToken: vi.fn(() => 'test-token'),
}));

vi.mock('../../../utils/tokenManager', () => ({
  tokenManager: {
    getAccessToken,
  },
}));

import SMSEmail2FA from '../SMSEmail2FA.jsx';

describe('SMSEmail2FA', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: 'access-token' }),
      });
  });

  it('sends 2FA requests via query-string contract expected by backend', async () => {
    const onSuccess = vi.fn();

    render(
      <ThemeProvider>
        <SMSEmail2FA
          method="sms"
          phoneNumber="+998901234567"
          onSuccess={onSuccess}
        />
      </ThemeProvider>
    );

    fireEvent.click(await screen.findByRole('button', { name: /Отправить код/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        1,
        '/api/v1/2fa/send-code?method=sms&phone_number=%2B998901234567',
        {
          method: 'POST',
          headers: {
            Authorization: 'Bearer test-token',
          },
        }
      );
    });

    fireEvent.change(screen.getByPlaceholderText('000000'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Подтвердить код/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        2,
        '/api/v1/2fa/verify-code?method=sms&phone_number=%2B998901234567&code=123456',
        {
          method: 'POST',
          headers: {
            Authorization: 'Bearer test-token',
          },
        }
      );
    });

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith({ access_token: 'access-token' });
    });
  });
});
