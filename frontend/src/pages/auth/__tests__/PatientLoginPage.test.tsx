import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PatientLoginPage from '../PatientLoginPage';
import PatientBookingPage from '../../PatientBookingPage';

const authState = vi.hoisted(() => ({ current: { token: null as string | null, profile: null as Record<string, unknown> | null } }));
const passkey = vi.hoisted(() => ({ supported: false, authenticating: false, step: null as null | 'select' | 'confirm' | 'confirming', error: '', authenticate: vi.fn(), confirm: vi.fn(), cancel: vi.fn() }));
vi.mock('../../../hooks/useWebAuthn', () => ({
  useWebAuthn: () => ({ isSupported: passkey.supported, isAuthenticating: passkey.authenticating, authenticationStep: passkey.step, authenticate: passkey.authenticate, confirmAuthentication: passkey.confirm, cancelAuthentication: passkey.cancel, error: passkey.error }),
}));
vi.mock('../../../utils/tokenManager', () => ({ tokenManager: { getAccessToken: () => authState.current.token } }));

vi.mock('../../../api/patientAccess', () => ({
  requestPatientOtp: vi.fn(),
  verifyPatientOtp: vi.fn(),
  patientLogin: vi.fn(),
  verifyPatientTwoFactor: vi.fn(),
  requestActivationOtp: vi.fn(),
  confirmActivation: vi.fn(),
  issueActivationToken: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: { post: vi.fn(), get: vi.fn() },
  ensureCSRFToken: vi.fn(() => Promise.resolve()),
  getAuthSessionGeneration: vi.fn(() => 1),
}));

vi.mock('../../../stores/auth', () => ({
  getState: vi.fn(() => authState.current),
  setToken: vi.fn(),
  setProfile: vi.fn(),
  clearToken: vi.fn(),
  replaceAccessOnlySession: vi.fn((token: string, profile: Record<string, unknown>) => {
    authState.current = { token, profile };
  }),
}));

vi.mock('../../../api/publicBooking', async () => {
  const actual = await vi.importActual<typeof import('../../../api/publicBooking')>('../../../api/publicBooking');
  return {
    ...actual,
    getPendingPublicBookingLocale: vi.fn(() => null),
    getPublicBookingOptions: vi.fn(),
    getPublicBookingAvailability: vi.fn(),
    createPatientPublicBookingRequest: vi.fn(),
    resubmitPatientPublicBookingRequest: vi.fn(),
    getPublicBookingPath: (locale: string) => locale === 'ru' ? '/ru/booking' : '/booking',
  };
});

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'ru',
    setLanguage: vi.fn(),
    availableLanguages: [{ code: 'ru', name: 'Русский', flag: 'RU' }],
    t: (key: string, options?: Record<string, unknown>) =>
      options && 'phone' in options ? `${key}:${String(options.phone)}` : key,
  }),
}));

import {
  patientLogin,
  requestPatientOtp,
  verifyPatientOtp,
  verifyPatientTwoFactor,
} from '../../../api/patientAccess';
import { ensureCSRFToken } from '../../../api/client';
import { replaceAccessOnlySession, setProfile, setToken } from '../../../stores/auth';
import {
  clearPendingPublicBookingSelection,
  createPatientPublicBookingRequest,
  getPendingPublicBookingLocale,
  getPublicBookingAvailability,
  getPublicBookingOptions,
  resubmitPatientPublicBookingRequest,
} from '../../../api/publicBooking';

const mockedRequestOtp = vi.mocked(requestPatientOtp);
const mockedVerifyOtp = vi.mocked(verifyPatientOtp);
const mockedPatientLogin = vi.mocked(patientLogin);

function todayInTashkent() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tashkent', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function renderPage(initialEntry: string | { pathname: string; state?: unknown } = '/patient/login') {
  const LocationProbe = () => {
    const location = useLocation();
    return (
      <>
        <output data-testid="current-path">{location.pathname}</output>
        <output data-testid="current-state">{JSON.stringify(location.state ?? null)}</output>
      </>
    );
  };
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ThemeProvider>
        <LocationProbe />
        <Routes>
          <Route path="/patient/login" element={<PatientLoginPage />} />
          <Route path="/ru/booking" element={<PatientBookingPage />} />
          <Route path="/booking" element={<PatientBookingPage />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>
  );
}

const PATIENT_SESSION = {
  access_token: 'patient-jwt',
  token_type: 'bearer',
  user: {
    id: 42,
    username: 'patient-42',
    email: null,
    full_name: 'Test Patient',
    role: 'Patient',
    is_active: true,
    is_superuser: false,
  },
};

describe('PatientLoginPage (Phase 0 PR-B)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.current = { token: null, profile: null };
    passkey.supported = false;
    passkey.authenticating = false;
    passkey.step = null;
    passkey.confirm.mockReset();
    passkey.cancel.mockReset();
    passkey.error = '';
    passkey.authenticate.mockReset();
    clearPendingPublicBookingSelection();
    mockedRequestOtp.mockResolvedValue({
      success: true,
      message: 'ok',
      expires_in_minutes: 5,
      resend_after_seconds: 60,
    });
    mockedVerifyOtp.mockResolvedValue({
      success: true,
      verification_grant: 'grant-token-32-chars-min',
      expires_in: 120,
    });
    mockedPatientLogin.mockResolvedValue(PATIENT_SESSION);
    vi.mocked(getPendingPublicBookingLocale).mockReturnValue(null);
    vi.mocked(getPublicBookingOptions).mockResolvedValue({
      settings_version: 1,
      available: true,
      mode: 'registrar_request',
      booking_horizon_days: 90,
      services: [{ slug: 'cardiology', name: 'Кардиология' }],
      doctors: [{ slug: 'doctor-one', name: 'Врач Один' }],
      compatible_pairs: [{ service_slug: 'cardiology', doctor_slug: 'doctor-one' }],
    } as never);
    vi.mocked(getPublicBookingAvailability).mockImplementation(async ({ date }) => ({
      date,
      timezone: 'Asia/Tashkent',
      settings_version: 1,
      slots: ['09:00:00'],
    }) as never);
    vi.mocked(createPatientPublicBookingRequest).mockResolvedValue({ id: 'new-request' } as never);
    vi.mocked(resubmitPatientPublicBookingRequest).mockResolvedValue({ id: 'same-request', status: 'pending' } as never);
  });

  it.each(['sms', 'passkey'])('requires a second factor after %s before installing a session', async (method) => {
    const pending = { requires_2fa: true as const, two_factor_method: 'totp' as const, pending_2fa_token: 'pending', user: PATIENT_SESSION.user };
    if (method === 'sms') mockedPatientLogin.mockResolvedValueOnce(pending);
    else { passkey.supported = true; passkey.authenticate.mockResolvedValueOnce(pending); }
    vi.mocked(verifyPatientTwoFactor).mockResolvedValueOnce({ success: false }).mockResolvedValueOnce({ success: true, access_token: 'verified', token_type: 'bearer' });
    renderPage();
    if (method === 'sms') {
      fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), { target: { value: '+998901234567' } });
      fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_send_code' }));
      fireEvent.change(await screen.findByLabelText('patientPortal.pl_code_label'), { target: { value: '123456' } });
      fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_verify' }));
    } else fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_login' }));
    const input = await screen.findByLabelText('patientPortal.pl_totp_label');
    expect(replaceAccessOnlySession).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_second_factor_submit' }));
    expect(await screen.findByText('patientPortal.pl_second_factor_invalid')).toBeInTheDocument();
    expect(replaceAccessOnlySession).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('patientPortal.pl_backup_option'));
    fireEvent.change(screen.getByLabelText('patientPortal.pl_backup_label'), { target: { value: 'aBcd-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_second_factor_submit' }));
    await waitFor(() => expect(replaceAccessOnlySession).toHaveBeenCalledWith('verified', PATIENT_SESSION.user));
    expect(verifyPatientTwoFactor).toHaveBeenLastCalledWith({ pending_2fa_token: 'pending', backup_code: 'aBcd-123' });
  });

  it('discards a pending factor result when another session starts', async () => {
    passkey.supported = true;
    passkey.authenticate.mockResolvedValueOnce({ requires_2fa: true, two_factor_method: 'totp', pending_2fa_token: 'pending', user: PATIENT_SESSION.user });
    let resolve!: (v: { success: true; access_token: string; token_type: string }) => void;
    vi.mocked(verifyPatientTwoFactor).mockImplementationOnce(() => new Promise((r) => { resolve = r; }));
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_login' }));
    fireEvent.change(await screen.findByLabelText('patientPortal.pl_totp_label'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_second_factor_submit' }));
    authState.current = { token: 'new-session', profile: null };
    fireEvent(window, new Event('authStateChanged'));
    resolve({ success: true, access_token: 'late-token', token_type: 'bearer' });
    await waitFor(() => expect(screen.getByLabelText('patientPortal.pl_phone_label')).toBeInTheDocument());
    expect(replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it.each([
    [401, 'patientPortal.pl_second_factor_expired'],
    [429, 'patientPortal.pl_rate_limited'],
    [503, 'patientPortal.pl_unavailable'],
  ])('reports factor verification status %s safely', async (status, message) => {
    passkey.supported = true;
    passkey.authenticate.mockResolvedValueOnce({ requires_2fa: true, two_factor_method: 'totp', pending_2fa_token: 'pending', user: PATIENT_SESSION.user });
    vi.mocked(verifyPatientTwoFactor).mockRejectedValueOnce({ response: { status } });
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_login' }));
    fireEvent.change(await screen.findByLabelText('patientPortal.pl_totp_label'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_second_factor_submit' }));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(replaceAccessOnlySession).not.toHaveBeenCalled();
    if (status === 401) expect(screen.getByLabelText('patientPortal.pl_phone_label')).toBeInTheDocument();
    else expect(screen.getByLabelText('patientPortal.pl_totp_label')).toHaveValue('');
  });

  it('cancels a pending challenge and clears the factor input', async () => {
    passkey.supported = true;
    passkey.authenticate.mockResolvedValueOnce({ requires_2fa: true, two_factor_method: 'totp', pending_2fa_token: 'pending', user: PATIENT_SESSION.user });
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_login' }));
    fireEvent.change(await screen.findByLabelText('patientPortal.pl_totp_label'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_second_factor_cancel' }));
    expect(screen.getByLabelText('patientPortal.pl_phone_label')).toBeInTheDocument();
    expect(verifyPatientTwoFactor).not.toHaveBeenCalled();
    expect(replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('does not install a pending factor response after unmount', async () => {
    passkey.supported = true;
    passkey.authenticate.mockResolvedValueOnce({ requires_2fa: true, two_factor_method: 'totp', pending_2fa_token: 'pending', user: PATIENT_SESSION.user });
    let resolve!: (v: { success: true; access_token: string; token_type: string }) => void;
    vi.mocked(verifyPatientTwoFactor).mockImplementationOnce(() => new Promise((r) => { resolve = r; }));
    const { unmount } = renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_login' }));
    fireEvent.change(await screen.findByLabelText('patientPortal.pl_totp_label'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_second_factor_submit' }));
    unmount();
    resolve({ success: true, access_token: 'late-token', token_type: 'bearer' });
    await Promise.resolve();
    expect(replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('offers discoverable passkey login while retaining phone OTP', async () => {
    passkey.supported = true;
    passkey.authenticate.mockResolvedValue(PATIENT_SESSION);
    renderPage();
    expect(screen.getByLabelText('patientPortal.pl_phone_label')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_login' }));
    await waitFor(() => expect(screen.getByTestId('current-path')).toHaveTextContent('/patient'));
    expect(passkey.authenticate).toHaveBeenCalledWith({ isCurrent: expect.any(Function) });
    expect(mockedRequestOtp).not.toHaveBeenCalled();
  });

  it.each([
    ['authentication_unavailable', 'patientPortal.pl_unavailable'],
    ['authentication_rate_limited', 'patientPortal.pl_rate_limited'],
  ])('shows %s while keeping the OTP form available', async (reason, message) => {
    passkey.supported = true;
    passkey.error = reason;
    passkey.authenticate.mockResolvedValue(null);
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_login' }));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.getByLabelText('patientPortal.pl_send_code')).toBeEnabled();
  });

  it('blocks an OTP request while passkey authentication is pending', async () => {
    passkey.supported = true;
    let resolvePasskey: (value: null) => void = () => {};
    passkey.authenticate.mockReturnValue(new Promise((resolve) => { resolvePasskey = resolve; }));
    renderPage();
    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), { target: { value: '+998900000000' } });
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_login' }));
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_send_code').closest('form')!);
    expect(mockedRequestOtp).not.toHaveBeenCalled();
    resolvePasskey(null);
    await waitFor(() => expect(screen.getByLabelText('patientPortal.pl_send_code')).toBeEnabled());
  });

  it('keeps OTP available when this browser lacks passkey support', () => {
    renderPage();
    expect(screen.queryByRole('button', { name: 'patient.pat_web_login' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('patientPortal.pl_send_code')).toBeEnabled();
  });

  it('announces the second system confirmation while it is pending', () => {
    passkey.supported = true;
    passkey.authenticating = true;
    passkey.step = 'confirm';
    renderPage();
    expect(screen.getByText('patient.pat_web_second_confirmation')).toBeInTheDocument();
    const continueButton = screen.getByRole('button', { name: 'patient.pat_web_continue_confirmation' });
    expect(continueButton).toHaveFocus();
    fireEvent.click(continueButton);
    expect(passkey.confirm).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_cancel' }));
    expect(passkey.cancel).toHaveBeenCalledTimes(1);
  });

  it('does not replace a session changed during OTP verification', async () => {
    let resolveVerify: (value: Awaited<ReturnType<typeof verifyPatientOtp>>) => void = () => {};
    mockedVerifyOtp.mockReturnValueOnce(new Promise((resolve) => { resolveVerify = resolve; }));
    renderPage();
    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), { target: { value: '+998900000000' } });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_send_code').closest('form')!);
    fireEvent.change(await screen.findByLabelText('patientPortal.pl_code_label'), { target: { value: '123456' } });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_verify').closest('form')!);
    authState.current = { token: 'newer-session', profile: { role: 'Admin' } };
    resolveVerify({ success: true, verification_grant: 'synthetic-grant', expires_in: 120 });
    await waitFor(() => expect(screen.getByLabelText('patientPortal.pl_verify')).toBeEnabled());
    expect(mockedPatientLogin).not.toHaveBeenCalled();
    expect(replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('does not install an OTP session if authentication changes while login finishes', async () => {
    mockedPatientLogin.mockImplementationOnce(async () => {
      window.dispatchEvent(new CustomEvent('authStateChanged'));
      return PATIENT_SESSION;
    });
    renderPage();
    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), { target: { value: '+998900000000' } });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_send_code').closest('form')!);
    fireEvent.change(await screen.findByLabelText('patientPortal.pl_code_label'), { target: { value: '123456' } });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_verify').closest('form')!);
    await waitFor(() => expect(screen.getByLabelText('patientPortal.pl_verify')).toBeEnabled());
    expect(mockedPatientLogin).toHaveBeenCalled();
    expect(replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('renders the phone step and rejects an invalid phone client-side', async () => {
    renderPage();

    const phoneInput = screen.getByLabelText('patientPortal.pl_phone_label');
    expect(phoneInput).toBeInTheDocument();

    fireEvent.change(phoneInput, { target: { value: '12345' } });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_send_code').closest('form')!);

    expect(await screen.findByText('patientPortal.pl_phone_invalid')).toBeInTheDocument();
    expect(mockedRequestOtp).not.toHaveBeenCalled();
  });

  it('sends OTP for a valid phone and advances to the code step', async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), {
      target: { value: '+998 (90) 123-45-67' },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_send_code').closest('form')!);

    await waitFor(() => {
      expect(mockedRequestOtp).toHaveBeenCalledWith({
        phone: '+998901234567',
        locale: 'ru',
      });
    });

    expect(await screen.findByLabelText('patientPortal.pl_code_label')).toBeInTheDocument();
    expect(screen.getByText('patientPortal.pl_code_sent_to:+998901234567')).toBeInTheDocument();
  });

  it('verifies OTP, exchanges the grant for a patient session and stores it', async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), {
      target: { value: '+998901234567' },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_send_code').closest('form')!);
    await screen.findByLabelText('patientPortal.pl_code_label');

    fireEvent.change(screen.getByLabelText('patientPortal.pl_code_label'), {
      target: { value: '123456' },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_verify').closest('form')!);

    await waitFor(() => {
      expect(mockedPatientLogin).toHaveBeenCalledWith({
        phone: '+998901234567',
        verification_grant: 'grant-token-32-chars-min',
      });
    });

    await waitFor(() => {
      // P1: the canonical session is installed via the access-only
      // replacement helper (which also clears any stale staff refresh
      // token) — never via the raw setToken/setProfile pair.
      expect(replaceAccessOnlySession).toHaveBeenCalledWith('patient-jwt', PATIENT_SESSION.user);
      expect(ensureCSRFToken).toHaveBeenCalled();
      expect(setToken).not.toHaveBeenCalled();
      expect(setProfile).not.toHaveBeenCalled();
    });
  });

  it('rejects a non-6-digit code client-side without API calls', async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), {
      target: { value: '+998901234567' },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_send_code').closest('form')!);
    await screen.findByLabelText('patientPortal.pl_code_label');

    fireEvent.change(screen.getByLabelText('patientPortal.pl_code_label'), {
      target: { value: '12ab' },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_verify').closest('form')!);

    expect(await screen.findByText('patientPortal.pl_code_invalid')).toBeInTheDocument();
    expect(mockedVerifyOtp).not.toHaveBeenCalled();
  });

  it('returns to the selected booking after patient login when a selection is pending', async () => {
    vi.mocked(getPendingPublicBookingLocale).mockReturnValue('ru');
    renderPage();

    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), {
      target: { value: '+998901234567' },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_send_code').closest('form')!);
    await screen.findByLabelText('patientPortal.pl_code_label');
    fireEvent.change(screen.getByLabelText('patientPortal.pl_code_label'), { target: { value: '123456' } });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_verify').closest('form')!);

    await waitFor(() => expect(screen.getByTestId('current-path')).toHaveTextContent('/ru/booking'));
  });

  it('resubmits the same request after the patient signs in again', async () => {
    const requestId = '3d7bdb53-c26e-46ed-81ec-9e7bdebd12ab';
    renderPage({
      pathname: '/ru/booking',
      state: {
        publicBookingResubmit: {
          requestId,
          expectedVersion: 6,
          serviceSlug: 'cardiology',
          doctorSlug: 'doctor-one',
        },
      },
    });

    await screen.findByLabelText('Услуга');
    fireEvent.change(screen.getByLabelText('Дата'), { target: { value: todayInTashkent() } });
    fireEvent.click(await screen.findByLabelText('09:00'));
    fireEvent.click(screen.getByRole('button', { name: 'Войти как пациент' }));

    expect(screen.getByTestId('current-path')).toHaveTextContent('/patient/login');
    const loginState = JSON.parse(screen.getByTestId('current-state').textContent ?? 'null');
    expect(loginState.publicBookingResubmitRequired).toBe(true);
    expect(loginState.publicBookingResubmit.requestId).toBe(requestId);
    expect(loginState.publicBookingResubmit.expectedVersion).toBe(6);
    expect(loginState.publicBookingResubmit.createdAt).toEqual(expect.any(Number));

    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), {
      target: { value: '+998901234567' },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_send_code').closest('form')!);
    await screen.findByLabelText('patientPortal.pl_code_label');
    fireEvent.change(screen.getByLabelText('patientPortal.pl_code_label'), { target: { value: '123456' } });
    fireEvent.submit(screen.getByLabelText('patientPortal.pl_verify').closest('form')!);

    await screen.findByRole('button', { name: 'Отправить новое время' });
    expect(screen.getByTestId('current-path')).toHaveTextContent('/ru/booking');
    const returnedState = JSON.parse(screen.getByTestId('current-state').textContent ?? 'null');
    expect(returnedState.publicBookingResubmit.requestId).toBe(requestId);
    expect(returnedState.publicBookingResubmit.expectedVersion).toBe(6);

    const resubmitButton = screen.getByRole('button', { name: 'Отправить новое время' });
    await waitFor(() => expect(resubmitButton).toBeEnabled());
    fireEvent.click(resubmitButton);
    await screen.findByRole('heading', { name: /Новое время отправлено регистратору/ });

    expect(resubmitPatientPublicBookingRequest).toHaveBeenCalledTimes(1);
    expect(vi.mocked(resubmitPatientPublicBookingRequest).mock.calls[0][0]).toBe(requestId);
    expect(vi.mocked(resubmitPatientPublicBookingRequest).mock.calls[0][1]).toMatchObject({
      expected_version: 6,
      appointment_date: todayInTashkent(),
      appointment_time: '09:00',
      expected_settings_version: 1,
    });
    expect(createPatientPublicBookingRequest).not.toHaveBeenCalled();
  });
});
