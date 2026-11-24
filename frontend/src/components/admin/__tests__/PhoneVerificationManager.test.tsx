import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';

const { apiGet, apiPost, logError, toastError, toastSuccess } = vi.hoisted(() => ({
  apiGet: vi.fn(), apiPost: vi.fn(), logError: vi.fn(), toastError: vi.fn(), toastSuccess: vi.fn(),
}));

vi.mock('../../../api/client', () => ({ api: { get: apiGet, post: apiPost } }));
vi.mock('../../../utils/logger', () => ({ default: { error: logError, info: vi.fn(), warn: vi.fn(), debug: vi.fn() } }));
vi.mock('react-toastify', () => ({ toast: { error: toastError, success: toastSuccess } }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

import PhoneVerificationManager from '../PhoneVerificationManager';

describe('PhoneVerificationManager private request contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGet.mockResolvedValue({ data: { statistics: {} } });
    apiPost.mockResolvedValue({ data: { success: true } });
  });

  it('sends the phone and custom message in the request body only', async () => {
    render(<ThemeProvider><PhoneVerificationManager /></ThemeProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.pvm_tab_tools' }));
    const phone = `+998${'0'.repeat(9)}`;
    const message = 'SYNTHETIC message sentinel';
    fireEvent.change(screen.getByPlaceholderText('+998XXXXXXXXX'), { target: { value: phone } });
    fireEvent.change(screen.getByPlaceholderText('admin2.pvm_ph_message'), { target: { value: message } });
    fireEvent.click(screen.getByRole('button', { name: 'Send admin verification code' }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/phone-verification/admin/send-code', {
      phone, purpose: 'verification', message,
    }));
    expect(apiPost.mock.calls[0]).toHaveLength(2);
  });

  it('offers only purposes and providers supported for administrator issuance', async () => {
    render(<ThemeProvider><PhoneVerificationManager /></ThemeProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.pvm_tab_tools' }));

    fireEvent.click(screen.getByRole('button', { name: 'admin2.pvm_purpose_verification' }));
    const purposes = within(screen.getByRole('listbox')).getAllByRole('option');
    expect(purposes.map((option) => option.textContent)).toEqual([
      'admin2.pvm_purpose_verification',
      'admin2.pvm_purpose_phone_change',
    ]);
    fireEvent.click(purposes[1]);

    fireEvent.click(screen.getByRole('button', { name: 'admin2.pvm_provider_default' }));
    const providers = within(screen.getByRole('listbox')).getAllByRole('option');
    expect(providers.map((option) => option.textContent)).toEqual([
      'admin2.pvm_provider_default', 'Eskiz', 'PlayMobile',
    ]);
    fireEvent.click(providers[1]);

    const phone = `+998${'0'.repeat(9)}`;
    fireEvent.change(screen.getByPlaceholderText('+998XXXXXXXXX'), { target: { value: phone } });
    fireEvent.click(screen.getByRole('button', { name: 'Send admin verification code' }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/phone-verification/admin/send-code', {
      phone, purpose: 'phone_change', provider: 'eskiz',
    }));
  });

  it('does not pass request errors or their embedded body to the logger', async () => {
    apiPost.mockRejectedValueOnce(new Error('synthetic-private-sentinel'));
    render(<ThemeProvider><PhoneVerificationManager /></ThemeProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.pvm_tab_tools' }));
    fireEvent.change(screen.getByPlaceholderText('+998XXXXXXXXX'), { target: { value: `+998${'0'.repeat(9)}` } });
    fireEvent.click(screen.getByRole('button', { name: 'Send admin verification code' }));
    await waitFor(() => expect(logError).toHaveBeenCalledWith('Error sending admin verification code'));
    expect(JSON.stringify(logError.mock.calls)).not.toContain('synthetic-private-sentinel');
  });
});
