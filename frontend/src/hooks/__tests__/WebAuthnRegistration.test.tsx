import { act, fireEvent, render, screen } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ post: vi.fn(), requestOtp: vi.fn(), verifyOtp: vi.fn(), getToken: vi.fn() }));

vi.mock('../../api/client', () => ({
  api: { post: mocks.post },
  ensureCSRFToken: vi.fn(),
}));
vi.mock('../../stores/auth', () => ({ replaceAccessOnlySession: vi.fn() }));
vi.mock('../../utils/tokenManager', () => ({ tokenManager: { getAccessToken: mocks.getToken } }));
vi.mock('../../api/patientAccess', () => ({ requestPatientOtp: mocks.requestOtp, verifyPatientOtp: mocks.verifyOtp }));
vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({}) }));

import WebAuthnRegistration from '../../components/patient/WebAuthnRegistration';

beforeEach(() => {
  mocks.post.mockReset();
  mocks.requestOtp.mockReset().mockResolvedValue({});
  mocks.verifyOtp.mockReset().mockResolvedValue({ verification_grant: 'synthetic-grant' });
  mocks.getToken.mockReset().mockReturnValue('patient-token');
  vi.stubGlobal('PublicKeyCredential', class PublicKeyCredential {});
});
afterEach(() => vi.unstubAllGlobals());

describe('passkey management availability', () => {
  it('shows unavailable rather than an empty list or add form after a 503', async () => {
    mocks.post.mockRejectedValueOnce({ response: { status: 503 } });
    render(<WebAuthnRegistration />);

    expect(await screen.findByText('patient.pat_web_unavailable')).toBeInTheDocument();
    expect(screen.queryByText('patient.pat_web_empty')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'patient.pat_web_add_passkey' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.refresh' })).toBeInTheDocument();
  });

  it.each([{}, { credentials: [null] }, { credentials: [{ id: 1, name: {} }] }])(
    'treats malformed list responses as unavailable', async (data) => {
      mocks.post.mockResolvedValueOnce({ data });
      render(<WebAuthnRegistration />);

      expect(await screen.findByText('patient.pat_web_unavailable')).toBeInTheDocument();
      expect(screen.queryByText('patient.pat_web_empty')).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'patient.pat_web_add_passkey' })).not.toBeInTheDocument();
    },
  );

  it('shows the actual empty state and add form after a successful retry', async () => {
    mocks.post.mockRejectedValueOnce({ response: { status: 503 } });
    mocks.post.mockResolvedValueOnce({ data: { credentials: [] } });
    render(<WebAuthnRegistration />);

    fireEvent.click(await screen.findByRole('button', { name: 'common.refresh' }));
    expect(await screen.findByText('patient.pat_web_empty')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'patient.pat_web_add_passkey' })).toBeInTheDocument();
    expect(screen.queryByText('patient.pat_web_unavailable')).not.toBeInTheDocument();
  });

  it('shows existing credentials after a successful list response', async () => {
    mocks.post.mockResolvedValueOnce({ data: { credentials: [{ id: 1, name: 'Synthetic key' }] } });
    render(<WebAuthnRegistration />);

    expect(await screen.findByText('Synthetic key')).toBeInTheDocument();
    expect(screen.queryByText('patient.pat_web_empty')).not.toBeInTheDocument();
    expect(screen.queryByText('patient.pat_web_unavailable')).not.toBeInTheDocument();
  });

  it('does not let an older failed request overwrite a later successful list', async () => {
    let rejectOld: (reason: unknown) => void = () => { throw new Error('request not started'); };
    mocks.post.mockReturnValueOnce(new Promise((_resolve, reject) => { rejectOld = reject; }));
    mocks.post.mockResolvedValueOnce({ data: { credentials: [] } });
    render(<StrictMode><WebAuthnRegistration /></StrictMode>);

    expect(await screen.findByText('patient.pat_web_empty')).toBeInTheDocument();
    await act(async () => { rejectOld({ response: { status: 503 } }); });
    expect(screen.getByText('patient.pat_web_empty')).toBeInTheDocument();
    expect(screen.queryByText('patient.pat_web_unavailable')).not.toBeInTheDocument();
  });
});


describe('passkey step-up', () => {
  it('requires a new code before removing a passkey and refreshes the list', async () => {
    mocks.post.mockResolvedValueOnce({ data: { credentials: [{ id: 5, name: 'Synthetic key' }] } })
      .mockResolvedValueOnce({ data: {} }).mockResolvedValueOnce({ data: { credentials: [] } });
    render(<WebAuthnRegistration />);
    fireEvent.click(await screen.findByRole('button', { name: 'patient.pat_web_delete' }));
    expect(mocks.post).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), { target: { value: '+998900000000' } });
    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_send_code' }));
    const code = await screen.findByLabelText('patientPortal.pl_code_label');
    fireEvent.change(code, { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_confirm' }));
    expect(await screen.findByText('patient.pat_web_empty')).toBeInTheDocument();
    expect(mocks.verifyOtp).toHaveBeenCalledWith({ phone: '+998900000000', code: '123456' });
    expect(mocks.post).toHaveBeenNthCalledWith(2, '/webauthn/credentials/5/deactivate', { phone: '+998900000000', verification_grant: 'synthetic-grant' });
  });

  it('discards an OTP grant after auth state changes even when the token is unchanged', async () => {
    mocks.post.mockResolvedValueOnce({ data: { credentials: [{ id: 5 }] } });
    mocks.verifyOtp.mockImplementation(async () => {
      window.dispatchEvent(new CustomEvent('authStateChanged'));
      return { verification_grant: 'synthetic-grant' };
    });
    render(<WebAuthnRegistration />);
    fireEvent.click(await screen.findByRole('button', { name: 'patient.pat_web_delete' }));
    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), { target: { value: '+998900000000' } });
    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_send_code' }));
    fireEvent.change(await screen.findByLabelText('patientPortal.pl_code_label'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_confirm' }));
    expect(await screen.findByText('patient.pat_web_unavailable')).toBeInTheDocument();
    expect(mocks.post).toHaveBeenCalledTimes(1);
  });

  it('does not use a grant when the session changes during verification', async () => {
    mocks.post.mockResolvedValueOnce({ data: { credentials: [{ id: 5 }] } });
    mocks.verifyOtp.mockImplementation(async () => { mocks.getToken.mockReturnValue('other-token'); return { verification_grant: 'synthetic-grant' }; });
    render(<WebAuthnRegistration />);
    fireEvent.click(await screen.findByRole('button', { name: 'patient.pat_web_delete' }));
    fireEvent.change(screen.getByLabelText('patientPortal.pl_phone_label'), { target: { value: '+998900000000' } });
    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pl_send_code' }));
    fireEvent.change(await screen.findByLabelText('patientPortal.pl_code_label'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'patient.pat_web_confirm' }));
    expect(await screen.findByText('patient.pat_web_err_not_authenticated')).toBeInTheDocument();
    expect(mocks.post).toHaveBeenCalledTimes(1);
  });
});
