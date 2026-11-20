import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../client', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { api } from '../client';
import {
  confirmActivation,
  issueActivationToken,
  patientLogin,
  requestActivationOtp,
  requestPatientOtp,
  verifyPatientOtp,
  verifyPatientTwoFactor,
} from '../patientAccess';

const mockedPost = vi.mocked(api.post);

// Valid transport payloads (zod-validated by the mapper layer).
const OTP_SENT = {
  success: true,
  message: 'sent',
  expires_in_minutes: 5,
  resend_after_seconds: 60,
};

const GRANT = {
  success: true,
  verification_grant: 'grant-token-32-chars-min',
  expires_in: 120,
};

const SESSION = {
  access_token: 'patient-jwt',
  token_type: 'bearer',
  user: {
    id: 1,
    username: 'patient-1',
    email: null,
    full_name: null,
    role: 'Patient',
    is_active: true,
    is_superuser: false,
  },
};

const ACTIVATION_OTP_SENT = {
  success: true,
  phone_masked: '+998 *** *** 45 67',
  expires_in_minutes: 5,
  resend_after_seconds: 60,
};

const TOKEN_RESULT = {
  activation_token: 'f'.repeat(64),
  expires_in_hours: 72,
  phone_masked: '+998 *** *** 45 67',
};

describe('patientAccess API module (Phase 0 PR-B)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedPost.mockResolvedValue({ data: {} } as never);
  });

  it('posts login OTP to the canonical PR-A1 endpoint and validates the payload', async () => {
    mockedPost.mockResolvedValueOnce({ data: OTP_SENT } as never);
    const result = await requestPatientOtp({ phone: '+998901234567', locale: 'ru' });
    expect(mockedPost).toHaveBeenCalledWith('/patient-access/request-otp', {
      phone: '+998901234567',
      locale: 'ru',
    });
    expect(result.resend_after_seconds).toBe(60);
  });

  it('verifies the OTP and returns the one-time grant', async () => {
    mockedPost.mockResolvedValueOnce({ data: GRANT } as never);
    const result = await verifyPatientOtp({ phone: '+998901234567', code: '123456' });
    expect(mockedPost).toHaveBeenCalledWith('/patient-access/verify-otp', {
      phone: '+998901234567',
      code: '123456',
    });
    expect(result.verification_grant).toBe('grant-token-32-chars-min');
  });

  it('posts grant login to the canonical PR-A1 endpoint and returns the session', async () => {
    mockedPost.mockResolvedValueOnce({ data: SESSION } as never);
    const result = await patientLogin({ phone: '+998901234567', verification_grant: 'grant' });
    expect(mockedPost).toHaveBeenCalledWith('/patient-access/login', {
      phone: '+998901234567',
      verification_grant: 'grant',
    });
    expect(result.user.role).toBe('Patient');
  });

  it('returns a token-free pending challenge and exchanges a backup code without changing it', async () => {
    const pending = { requires_2fa: true, two_factor_method: 'totp', pending_2fa_token: 'pending', user: SESSION.user };
    mockedPost.mockResolvedValueOnce({ data: pending } as never);
    expect(await patientLogin({ phone: '+998901234567', verification_grant: 'grant' })).toEqual(pending);
    mockedPost.mockResolvedValueOnce({ data: { success: true, access_token: 'patient-jwt', token_type: 'bearer', refresh_token: null } } as never);
    expect(await verifyPatientTwoFactor({ pending_2fa_token: 'pending', backup_code: 'aBcd-123' })).toEqual({ success: true, access_token: 'patient-jwt', token_type: 'bearer' });
    expect(mockedPost).toHaveBeenLastCalledWith('/2fa/verify', { pending_2fa_token: 'pending', backup_code: 'aBcd-123' });
  });

  it.each([
    { requires_2fa: true, two_factor_method: 'totp', pending_2fa_token: '', user: SESSION.user },
    { requires_2fa: true, two_factor_method: 'totp', pending_2fa_token: 'pending', user: SESSION.user, access_token: 'premature' },
    { requires_2fa: true, two_factor_method: 'totp', pending_2fa_token: 'pending', user: { ...SESSION.user, role: 'Admin' } },
  ])('rejects malformed or privileged pending challenges', async (data) => {
    mockedPost.mockResolvedValueOnce({ data } as never);
    await expect(patientLogin({ phone: '+998901234567', verification_grant: 'grant' })).rejects.toThrow();
  });

  it('never accepts a refresh token from the patient factor exchange', async () => {
    mockedPost.mockResolvedValueOnce({ data: { success: true, access_token: 'patient', token_type: 'bearer', refresh_token: 'staff' } } as never);
    await expect(verifyPatientTwoFactor({ pending_2fa_token: 'pending', totp_code: '123456' })).rejects.toThrow();
  });

  it('posts activation OTP request to the canonical PR-A2 endpoint', async () => {
    mockedPost.mockResolvedValueOnce({ data: ACTIVATION_OTP_SENT } as never);
    const result = await requestActivationOtp({ activation_token: 'tok', locale: 'ru' });
    expect(mockedPost).toHaveBeenCalledWith('/patient-access/activate/request-otp', {
      activation_token: 'tok',
      locale: 'ru',
    });
    expect(result.phone_masked).toBe('+998 *** *** 45 67');
  });

  it('posts activation confirm to the canonical PR-A2 endpoint', async () => {
    mockedPost.mockResolvedValueOnce({ data: { ...SESSION, patient_id: 7 } } as never);
    const result = await confirmActivation({ activation_token: 'tok', code: '123456' });
    expect(mockedPost).toHaveBeenCalledWith('/patient-access/activate/confirm', {
      activation_token: 'tok',
      code: '123456',
    });
    expect(result.patient_id).toBe(7);
  });

  it('issues staff activation tokens with an empty body on the path-only endpoint', async () => {
    mockedPost.mockResolvedValueOnce({ data: TOKEN_RESULT } as never);
    const result = await issueActivationToken(5);
    expect(mockedPost).toHaveBeenCalledWith('/patients/5/activation-token');
    expect(result.activation_token).toBe(TOKEN_RESULT.activation_token);
    expect(result.expires_in_hours).toBe(72);
  });
});
