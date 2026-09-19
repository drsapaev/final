import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PatientActivatePage from '../PatientActivatePage';

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
  confirmActivation,
  requestActivationOtp,
} from '../../../api/patientAccess';
import { setProfile, setToken } from '../../../stores/auth';

const mockedRequestOtp = vi.mocked(requestActivationOtp);
const mockedConfirm = vi.mocked(confirmActivation);

const TOKEN = 'a'.repeat(64);

function renderPage(initialEntries?: string[]) {
  return render(
    <MemoryRouter initialEntries={initialEntries ?? ['/patient/activate']}>
      <ThemeProvider>
        <PatientActivatePage />
      </ThemeProvider>
    </MemoryRouter>
  );
}

const PATIENT_SESSION = {
  access_token: 'activated-jwt',
  token_type: 'bearer',
  user: {
    id: 7,
    username: 'patient-7',
    email: null,
    full_name: 'Activated Patient',
    role: 'Patient',
    is_active: true,
    is_superuser: false,
  },
  patient_id: 7,
};

describe('PatientActivatePage (Phase 0 PR-B)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedRequestOtp.mockResolvedValue({
      success: true,
      phone_masked: '+998 *** *** 45 67',
      expires_in_minutes: 5,
      resend_after_seconds: 60,
    });
    mockedConfirm.mockResolvedValue(PATIENT_SESSION);
  });

  it('prefills the token from the ?token= deep-link but never auto-submits', () => {
    renderPage([`/patient/activate?token=${TOKEN}`]);

    const tokenInput = screen.getByLabelText('patientPortal.pa_token_label') as HTMLInputElement;
    expect(tokenInput.value).toBe(TOKEN);
    expect(mockedRequestOtp).not.toHaveBeenCalled();
  });

  it('rejects a too-short token client-side', async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText('patientPortal.pa_token_label'), {
      target: { value: 'short-token' },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pa_continue').closest('form')!);

    expect(await screen.findByText('patientPortal.pa_token_invalid')).toBeInTheDocument();
    expect(mockedRequestOtp).not.toHaveBeenCalled();
  });

  it('requests the activation OTP and shows the masked card phone', async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText('patientPortal.pa_token_label'), {
      target: { value: TOKEN },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pa_continue').closest('form')!);

    await waitFor(() => {
      expect(mockedRequestOtp).toHaveBeenCalledWith({ activation_token: TOKEN, locale: 'ru' });
    });

    expect(await screen.findByLabelText('patientPortal.pa_code_label')).toBeInTheDocument();
    expect(screen.getByText('patientPortal.pa_otp_sent_to:+998 *** *** 45 67')).toBeInTheDocument();
  });

  it('confirms the OTP, stores the canonical patient session', async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText('patientPortal.pa_token_label'), {
      target: { value: TOKEN },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pa_continue').closest('form')!);
    await screen.findByLabelText('patientPortal.pa_code_label');

    fireEvent.change(screen.getByLabelText('patientPortal.pa_code_label'), {
      target: { value: '654321' },
    });
    fireEvent.submit(screen.getByLabelText('patientPortal.pa_confirm').closest('form')!);

    await waitFor(() => {
      expect(mockedConfirm).toHaveBeenCalledWith({ activation_token: TOKEN, code: '654321' });
      expect(setToken).toHaveBeenCalledWith('activated-jwt');
      expect(setProfile).toHaveBeenCalledWith(PATIENT_SESSION.user);
    });
  });
});
