import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';

const { apiPost, apiPut, getAuthSessionGeneration, clearAuthToken, success, error, logError } = vi.hoisted(() => ({
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  getAuthSessionGeneration: vi.fn(),
  clearAuthToken: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  logError: vi.fn(),
}));

vi.mock('../../../api/client', () => ({ api: { post: apiPost, put: apiPut }, getAuthSessionGeneration }));
vi.mock('../../../stores/auth', () => ({ clearAuthToken }));
vi.mock('../../../utils/logger', () => ({ default: { error: logError, info: vi.fn(), warn: vi.fn(), debug: vi.fn() } }));
vi.mock('react-toastify', () => ({ toast: { success, error } }));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string, options?: { timeLeft?: string }) => options?.timeLeft ? `${key}:${options.timeLeft}` : key }),
}));

import PhoneVerification from '../PhoneVerification';

const syntheticPhone = `+998${'0'.repeat(9)}`;

function renderForm(props: React.ComponentProps<typeof PhoneVerification> = {}) {
  return render(<ThemeProvider><PhoneVerification {...props} /></ThemeProvider>);
}

async function startPhoneChange() {
  renderForm({ purpose: 'phone_change', showPhoneInput: true });
  fireEvent.change(screen.getByLabelText('misc.pv_nomer_telefona'), { target: { value: syntheticPhone } });
  fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otpravit_kod_podtverzhdeniya' }));
  await screen.findByLabelText('misc.pv_kod_verifikatsii');
  fireEvent.change(screen.getByLabelText('misc.pv_kod_verifikatsii'), { target: { value: '123456' } });
}

describe('PhoneVerification private request contracts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getAuthSessionGeneration.mockReturnValue(1);
    apiPost.mockResolvedValue({ data: { success: true, expires_in_minutes: 5 } });
    apiPut.mockResolvedValue({ data: { success: true, sessions_revoked: true } });
  });

  it('loads status through a JSON body, not a query string', async () => {
    apiPost.mockResolvedValueOnce({ data: { exists: false } });
    renderForm({ phone: syntheticPhone, purpose: 'phone_change' });
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/phone-verification/status', {
      phone: syntheticPhone, purpose: 'phone_change',
    }));
  });

  it('sends and cancels the challenge without putting the phone in the URL', async () => {
    await startPhoneChange();
    expect(apiPost).toHaveBeenCalledWith('/phone-verification/send-code', {
      phone: syntheticPhone, purpose: 'phone_change',
    });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otmenit' }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/phone-verification/cancel', {
      phone: syntheticPhone, purpose: 'phone_change',
    }));
    expect(apiPost.mock.calls.every(([url]) => !String(url).includes(syntheticPhone))).toBe(true);
  });

  it('keeps the submitted number fixed while SMS delivery is pending', async () => {
    let resolveSend!: (value: unknown) => void;
    apiPost.mockReturnValueOnce(new Promise((resolve) => { resolveSend = resolve; }));
    renderForm({ purpose: 'phone_change', showPhoneInput: true });
    const phoneInput = screen.getByLabelText('misc.pv_nomer_telefona');
    fireEvent.change(phoneInput, { target: { value: syntheticPhone } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otpravit_kod_podtverzhdeniya' }));
    expect(phoneInput).toBeDisabled();
    fireEvent.change(phoneInput, { target: { value: `+998${'0'.repeat(8)}1` } });

    await act(async () => { resolveSend({ data: { success: true, expires_in_seconds: 60 } }); });
    expect(screen.getByLabelText('misc.pv_nomer_telefona')).toHaveValue(syntheticPhone);
    fireEvent.change(screen.getByLabelText('misc.pv_kod_verifikatsii'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_podtverdit' }));
    await waitFor(() => expect(apiPut).toHaveBeenCalledWith('/phone-verification/update-phone', {
      new_phone: syntheticPhone, verification_code: '123456',
    }));
  });

  it('ignores a delayed send result after replacing the login session', async () => {
    let resolveSend!: (value: unknown) => void;
    apiPost.mockReturnValueOnce(new Promise((resolve) => { resolveSend = resolve; }));
    renderForm({ purpose: 'phone_change', showPhoneInput: true });
    fireEvent.change(screen.getByLabelText('misc.pv_nomer_telefona'), { target: { value: syntheticPhone } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otpravit_kod_podtverzhdeniya' }));
    getAuthSessionGeneration.mockReturnValue(2);
    await act(async () => { resolveSend({ data: { success: true, expires_in_seconds: 60 } }); });
    expect(screen.queryByLabelText('misc.pv_kod_verifikatsii')).not.toBeInTheDocument();
    expect(success).not.toHaveBeenCalled();
    expect(screen.getByLabelText('misc.pv_nomer_telefona')).not.toBeDisabled();
  });

  it('does not show a delayed send result after the form is unmounted', async () => {
    let resolveSend!: (value: unknown) => void;
    apiPost.mockReturnValueOnce(new Promise((resolve) => { resolveSend = resolve; }));
    const form = renderForm({ purpose: 'phone_change', showPhoneInput: true });
    fireEvent.change(screen.getByLabelText('misc.pv_nomer_telefona'), { target: { value: syntheticPhone } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otpravit_kod_podtverzhdeniya' }));
    form.unmount();
    await act(async () => { resolveSend({ data: { success: true, expires_in_seconds: 60 } }); });
    expect(success).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
  });

  it('uses the remaining seconds returned after a slow SMS delivery', async () => {
    apiPost.mockResolvedValueOnce({ data: { success: true, expires_in_seconds: 3, expires_in_minutes: 1 } });
    renderForm({ purpose: 'phone_change', showPhoneInput: true });
    fireEvent.change(screen.getByLabelText('misc.pv_nomer_telefona'), { target: { value: syntheticPhone } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otpravit_kod_podtverzhdeniya' }));
    expect(await screen.findByText('misc.pv_kod_deystvitelen_formattime_:0:03')).toBeInTheDocument();
  });

  it('does not present a challenge that has already expired', async () => {
    apiPost.mockResolvedValueOnce({ data: { success: true, expires_in_seconds: 0, expires_in_minutes: 1 } });
    renderForm({ purpose: 'phone_change', showPhoneInput: true });
    fireEvent.change(screen.getByLabelText('misc.pv_nomer_telefona'), { target: { value: syntheticPhone } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otpravit_kod_podtverzhdeniya' }));
    await waitFor(() => expect(error).toHaveBeenCalledWith('misc.pv_kod_istek_zaprosite_novyy_ko'));
    expect(screen.queryByLabelText('misc.pv_kod_verifikatsii')).not.toBeInTheDocument();
  });

  it('updates the profile once and clears the revoked session after a real change', async () => {
    await startPhoneChange();
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_podtverdit' }));
    await waitFor(() => expect(apiPut).toHaveBeenCalledWith('/phone-verification/update-phone', {
      new_phone: syntheticPhone, verification_code: '123456',
    }));
    expect(apiPost.mock.calls.some(([url]) => url === '/phone-verification/verify-code')).toBe(false);
    expect(clearAuthToken).toHaveBeenCalledOnce();
    expect(success).toHaveBeenCalledWith('misc.pv_phone_changed_relogin');
  });

  it('keeps the session when the server confirms no effective phone change', async () => {
    const onVerified = vi.fn();
    apiPut.mockResolvedValueOnce({ data: { success: true, sessions_revoked: false } });
    renderForm({ purpose: 'phone_change', showPhoneInput: true, onVerified });
    fireEvent.change(screen.getByLabelText('misc.pv_nomer_telefona'), { target: { value: syntheticPhone } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otpravit_kod_podtverzhdeniya' }));
    await screen.findByLabelText('misc.pv_kod_verifikatsii');
    fireEvent.change(screen.getByLabelText('misc.pv_kod_verifikatsii'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_podtverdit' }));
    await waitFor(() => expect(onVerified).toHaveBeenCalledWith(expect.objectContaining({
      phone: syntheticPhone, sessions_revoked: false,
    })));
    expect(clearAuthToken).not.toHaveBeenCalled();
  });

  it('fails closed for an ambiguous mixed-version update response', async () => {
    apiPut.mockResolvedValueOnce({ data: { success: true } });
    await startPhoneChange();
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_podtverdit' }));
    await waitFor(() => expect(clearAuthToken).toHaveBeenCalledOnce());
    expect(error).toHaveBeenCalledWith('misc.pv_phone_change_uncertain_relogin');
    expect(success).not.toHaveBeenCalledWith('misc.pv_phone_changed_relogin');
  });

  it('does not clear a replacement session after a late successful response', async () => {
    let resolveUpdate!: (value: unknown) => void;
    apiPut.mockReturnValueOnce(new Promise((resolve) => { resolveUpdate = resolve; }));
    await startPhoneChange();
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_podtverdit' }));
    await waitFor(() => expect(apiPut).toHaveBeenCalledOnce());
    const callsBeforeResolution = getAuthSessionGeneration.mock.calls.length;
    getAuthSessionGeneration.mockReturnValue(2);
    resolveUpdate({ data: { success: true, sessions_revoked: true } });
    await waitFor(() => expect(getAuthSessionGeneration.mock.calls.length).toBeGreaterThan(callsBeforeResolution));
    expect(clearAuthToken).not.toHaveBeenCalled();
    expect(success).not.toHaveBeenCalledWith('misc.pv_phone_changed_relogin');
  });

  it('requires re-login if a committed update response might have been lost', async () => {
    apiPut.mockRejectedValueOnce(new Error('synthetic-network-error'));
    await startPhoneChange();
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_podtverdit' }));
    await waitFor(() => expect(clearAuthToken).toHaveBeenCalledOnce());
    expect(error).toHaveBeenCalledWith('misc.pv_phone_change_uncertain_relogin');
  });

  it('does not clear a replacement session after a late failed response', async () => {
    let rejectUpdate!: (reason: Error) => void;
    apiPut.mockReturnValueOnce(new Promise((_resolve, reject) => { rejectUpdate = reject; }));
    await startPhoneChange();
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_podtverdit' }));
    await waitFor(() => expect(apiPut).toHaveBeenCalledOnce());
    const callsBeforeResolution = getAuthSessionGeneration.mock.calls.length;
    getAuthSessionGeneration.mockReturnValue(2);
    rejectUpdate(new Error('synthetic-network-error'));
    await waitFor(() => expect(getAuthSessionGeneration.mock.calls.length).toBeGreaterThan(callsBeforeResolution));
    expect(clearAuthToken).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalledWith('misc.pv_phone_change_uncertain_relogin');
  });

  it('keeps ordinary verification on its original endpoint', async () => {
    renderForm({ showPhoneInput: true });
    fireEvent.change(screen.getByLabelText('misc.pv_nomer_telefona'), { target: { value: syntheticPhone } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otpravit_kod_podtverzhdeniya' }));
    await screen.findByLabelText('misc.pv_kod_verifikatsii');
    fireEvent.change(screen.getByLabelText('misc.pv_kod_verifikatsii'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_podtverdit' }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/phone-verification/verify-code', {
      phone: syntheticPhone, code: '123456', purpose: 'verification',
    }));
    expect(apiPut).not.toHaveBeenCalled();
  });

  it('does not log the error object containing sensitive request details', async () => {
    apiPost.mockRejectedValueOnce(new Error('synthetic-private-sentinel'));
    renderForm({ showPhoneInput: true });
    fireEvent.change(screen.getByLabelText('misc.pv_nomer_telefona'), { target: { value: syntheticPhone } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pv_otpravit_kod_podtverzhdeniya' }));
    await waitFor(() => expect(logError).toHaveBeenCalledWith('Error sending verification code'));
    expect(JSON.stringify(logError.mock.calls)).not.toContain('synthetic-private-sentinel');
  });
});
