import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PatientLoginPage from '../PatientLoginPage';

vi.mock('../../../api/patientAccess', () => ({
  requestPatientOtp: vi.fn(),
  verifyPatientOtp: vi.fn(),
  patientLogin: vi.fn(),
  requestActivationOtp: vi.fn(),
  confirmActivation: vi.fn(),
  issueActivationToken: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: { post: vi.fn(), get: vi.fn() },
  ensureCSRFToken: vi.fn(() => Promise.resolve()),
}));

vi.mock('../../../stores/auth', () => ({
  setToken: vi.fn(),
  setProfile: vi.fn(),
  clearToken: vi.fn(),
}));

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
} from '../../../api/patientAccess';
import { ensureCSRFToken } from '../../../api/client';
import { setProfile, setToken } from '../../../stores/auth';

const mockedRequestOtp = vi.mocked(requestPatientOtp);
const mockedVerifyOtp = vi.mocked(verifyPatientOtp);
const mockedPatientLogin = vi.mocked(patientLogin);

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <PatientLoginPage />
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
      expect(setToken).toHaveBeenCalledWith('patient-jwt');
      expect(setProfile).toHaveBeenCalledWith(PATIENT_SESSION.user);
      expect(ensureCSRFToken).toHaveBeenCalled();
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
});
