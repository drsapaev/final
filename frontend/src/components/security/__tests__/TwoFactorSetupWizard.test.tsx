/**
 * TwoFactorSetupWizard — component contract tests.
 *
 * Covers the two-stage enrollment wiring and the reworked 3-step TOTP flow:
 * step 1 (recovery email + setup call), step 2 (REAL QR rendered from
 * qr_code_url + secret_key with the correct field name), step 3 (code entry
 * -> onEnrolled with tokens / onComplete for the profile flow), and error
 * surfacing.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiPostMock = vi.fn();

vi.mock('../../../api/client', () => ({
  api: { post: (...args: unknown[]) => apiPostMock(...args) },
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import TwoFactorSetupWizard from '../TwoFactorSetupWizard';

const setupPayload = {
  secret_key: 'JBSWY3DPEHPK3PXPTESTSECRET',
  qr_code_url: 'otpauth://totp/Clinic:admin@test?secret=JBSWY3DPEHPK3PXPTESTSECRET&issuer=Clinic',
  backup_codes: ['1111-1111', '2222-2222'],
};

const axiosOk = (data: Record<string, unknown>) => ({
  status: 200,
  statusText: 'OK',
  data,
  headers: {},
  config: {},
});

afterEach(() => {
  cleanup();
  apiPostMock.mockReset();
});

describe('TwoFactorSetupWizard', () => {
  it('renders step 1 with recovery email and no fake methods', () => {
    render(<TwoFactorSetupWizard />);
    expect(screen.getByText('misc.tfsw2_step1_title')).toBeTruthy();
    expect(screen.getByLabelText('2FA recovery email')).toBeTruthy();
    // SMS/Email fake methods removed — only the TOTP flow exists
    expect(screen.queryByText('misc.tfsw_method_sms_name')).toBeNull();
    expect(screen.queryByText('misc.tfsw_method_email_name')).toBeNull();
  });

  it('advances to QR step: renders a REAL QR and the secret_key field', async () => {
    apiPostMock.mockResolvedValueOnce(axiosOk(setupPayload));
    render(<TwoFactorSetupWizard />);

    fireEvent.click(screen.getByText('misc.tfsw_next'));

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledWith('/2fa/setup', { recovery_email: null });
    });
    await waitFor(() => {
      expect(screen.getByText('misc.tfsw2_step2_title')).toBeTruthy();
    });
    // QR is rendered by qrcode.react as an <svg> built from the otpauth URI
    const qr = document.querySelector('svg');
    expect(qr).toBeTruthy();
    // secret shown (masked by default) — reveal and check the correct field
    fireEvent.click(screen.getByLabelText('misc.tfsw_aria_show_secret'));
    expect(screen.getByText(/JBSWY3DPEHPK3PXPTESTSECRET/)).toBeTruthy();
  });

  it('completes enrollment: backup codes shown BEFORE onEnrolled exchange', async () => {
    apiPostMock
      .mockResolvedValueOnce(axiosOk(setupPayload))
      .mockResolvedValueOnce(
        axiosOk({ success: true, access_token: 'at', refresh_token: 'rt', token_type: 'bearer', expires_in: 1800 }),
      );
    const onEnrolled = vi.fn();
    render(<TwoFactorSetupWizard enrollmentToken="enroll-tok" onEnrolled={onEnrolled} />);

    fireEvent.click(screen.getByText('misc.tfsw_next'));
    await waitFor(() => screen.getByText('misc.tfsw2_step2_title'));
    fireEvent.click(screen.getByText('misc.tfsw_next'));

    const codeInput = screen.getByLabelText('2FA verification code');
    fireEvent.change(codeInput, { target: { value: '123456' } });
    fireEvent.click(screen.getByText('misc.tfsw_confirm_button'));

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledWith('/2fa/verify-setup', {
        totp_code: '123456',
        enrollment_token: 'enroll-tok',
      });
    });
    // Успех → сначала экран с резервными кодами, сессия ещё не завершена
    await waitFor(() => screen.getByText('misc.tfsw_step5_title'));
    expect(screen.getByText('1111-1111')).toBeTruthy();
    expect(onEnrolled).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText('misc.tfsw_finish_button'));
    await waitFor(() => {
      expect(onEnrolled).toHaveBeenCalledWith(
        expect.objectContaining({ access_token: 'at', refresh_token: 'rt' }),
      );
    });
  });

  it('profile flow (no enrollment token): success screen -> onComplete', async () => {
    apiPostMock
      .mockResolvedValueOnce(axiosOk(setupPayload))
      .mockResolvedValueOnce(axiosOk({ success: true }));
    const onComplete = vi.fn();
    render(<TwoFactorSetupWizard onComplete={onComplete} />);

    fireEvent.click(screen.getByText('misc.tfsw_next'));
    await waitFor(() => screen.getByText('misc.tfsw2_step2_title'));
    fireEvent.click(screen.getByText('misc.tfsw_next'));
    fireEvent.change(screen.getByLabelText('2FA verification code'), { target: { value: '654321' } });
    fireEvent.click(screen.getByText('misc.tfsw_confirm_button'));

    await waitFor(() => screen.getByText('misc.tfsw_step5_title'));
    expect(screen.getByText('1111-1111')).toBeTruthy();
    fireEvent.click(screen.getByText('misc.tfsw_finish_button'));
    expect(onComplete).toHaveBeenCalled();
  });

  it('surfaces setup errors in an alert region', async () => {
    apiPostMock.mockResolvedValueOnce(axiosOk({ detail: 'boom' }));
    render(<TwoFactorSetupWizard />);
    fireEvent.click(screen.getByText('misc.tfsw_next'));
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain('boom');
    });
  });
});
