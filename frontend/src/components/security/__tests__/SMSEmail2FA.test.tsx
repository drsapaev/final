import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext';

const { apiPostMock } = vi.hoisted(() => ({ apiPostMock: vi.fn() }));

vi.mock('../../../api/client', () => ({
  api: { post: (...args: unknown[]) => apiPostMock(...args) },
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import SMSEmail2FA from '../SMSEmail2FA';

afterEach(() => {
  cleanup();
  apiPostMock.mockReset();
});

describe('SMSEmail2FA API contract', () => {
  it('sends only the method and renders the masked destination from Axios data', async () => {
    apiPostMock.mockResolvedValueOnce({
      data: { success: true, destination: '••••4567' },
    });
    render(
      <ThemeProvider>
        <SMSEmail2FA method="sms" />
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'misc.sef_otpravit_kod' }));

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledWith('/2fa/send-code', { method: 'sms' });
    });
    expect(await screen.findByText('••••4567')).toBeTruthy();
  });

  it('verifies with an Axios body and forwards response.data', async () => {
    apiPostMock
      .mockResolvedValueOnce({ data: { success: true, destination: '••••4567' } })
      .mockResolvedValueOnce({ data: { success: true, verified: true, method: 'sms' } });
    const onSuccess = vi.fn();
    render(
      <ThemeProvider>
        <SMSEmail2FA method="sms" onSuccess={onSuccess} />
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'misc.sef_otpravit_kod' }));
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('misc.sef_kod_podtverzhdeniya'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Подтвердить код/ }));

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenLastCalledWith('/2fa/verify-code', {
        method: 'sms',
        code: '123456',
      });
      expect(onSuccess).toHaveBeenCalledWith({
        success: true,
        verified: true,
        method: 'sms',
      });
    });
  });
});
