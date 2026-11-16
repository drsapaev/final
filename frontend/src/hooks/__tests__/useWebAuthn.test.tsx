import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  post: vi.fn(),
  ensureCSRFToken: vi.fn(),
  replaceAccessOnlySession: vi.fn(),
  getAccessToken: vi.fn(),
  getCredential: vi.fn(),
  createCredential: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  api: { post: mocks.post },
  ensureCSRFToken: mocks.ensureCSRFToken,
}));
vi.mock('../../stores/auth', () => ({
  replaceAccessOnlySession: mocks.replaceAccessOnlySession,
}));
vi.mock('../../utils/tokenManager', () => ({
  tokenManager: { getAccessToken: mocks.getAccessToken },
}));

import useWebAuthn from '../useWebAuthn';

const patient = {
  id: 42,
  username: 'synthetic-patient',
  email: null,
  full_name: null,
  role: 'Patient',
  is_active: true,
  is_superuser: false,
};
const options = {
  challenge: 'AAH-_w',
  rpId: 'clinic.example',
  ceremony_id: 'synthetic-ceremony-id',
  timeout: 60000,
};
const session = { access_token: ' patient-access ', token_type: 'bearer', user: patient };
const assertion = {
  id: 'AQI',
  rawId: new Uint8Array([1, 2]).buffer,
  type: 'public-key',
  response: {
    authenticatorData: new Uint8Array([3]).buffer,
    clientDataJSON: new Uint8Array([4]).buffer,
    signature: new Uint8Array([5]).buffer,
    userHandle: null,
  },
};
const originalCredentials = Object.getOwnPropertyDescriptor(navigator, 'credentials');

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('PublicKeyCredential', class PublicKeyCredential {});
  Object.defineProperty(navigator, 'credentials', {
    configurable: true,
    value: { get: mocks.getCredential, create: mocks.createCredential },
  });
  mocks.getAccessToken.mockReturnValue('prior-staff-token');
  mocks.ensureCSRFToken.mockResolvedValue(null);
  mocks.getCredential.mockResolvedValue(assertion);
  mocks.post.mockResolvedValueOnce({ data: { options } }).mockResolvedValueOnce({ data: session });
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalCredentials) {
    Object.defineProperty(navigator, 'credentials', originalCredentials);
  } else {
    Reflect.deleteProperty(navigator, 'credentials');
  }
});

describe('passkey patient session', () => {
  it('passes the one-time ceremony and installs the canonical patient session', async () => {
    const { result } = renderHook(() => useWebAuthn());
    let returned: unknown;
    await act(async () => { returned = await result.current.authenticate({ patientId: '7' }); });

    expect(mocks.post).toHaveBeenNthCalledWith(1, '/webauthn/login/begin', { patient_id: '7' });
    expect(mocks.getCredential).toHaveBeenCalledWith({
      publicKey: expect.objectContaining({
        rpId: 'clinic.example',
        challenge: new Uint8Array([0, 1, 254, 255]).buffer,
      }),
    });
    expect(mocks.post).toHaveBeenNthCalledWith(2, '/webauthn/login/finish', {
      patient_id: '7',
      ceremony_id: 'synthetic-ceremony-id',
      assertion_response: expect.objectContaining({ id: 'AQI', rawId: 'AQI' }),
    });
    expect(mocks.replaceAccessOnlySession).toHaveBeenCalledWith('patient-access', patient);
    expect(returned).toMatchObject({ access_token: 'patient-access', user: patient });
    expect(sessionStorage.getItem('patient_jwt_token')).toBeNull();
    expect(sessionStorage.getItem('patient_refresh_token')).toBeNull();
    expect(result.current.error).toBe('');
  });

  it('signs in with a discoverable credential without patient identifiers', async () => {
    const { result } = renderHook(() => useWebAuthn());
    let returned: unknown;
    await act(async () => { returned = await result.current.authenticate(); });
    expect(mocks.post).toHaveBeenNthCalledWith(1, '/webauthn/login/discoverable/begin', {});
    expect(mocks.post).toHaveBeenNthCalledWith(2, '/webauthn/login/discoverable/finish', {
      ceremony_id: 'synthetic-ceremony-id', assertion_response: expect.objectContaining({ id: 'AQI' }),
    });
    expect(returned).toMatchObject({ access_token: 'patient-access' });
    expect(mocks.replaceAccessOnlySession).toHaveBeenCalledWith('patient-access', patient);
  });

  it('does not finish a discoverable ceremony after its login page is abandoned', async () => {
    let current = true;
    mocks.getCredential.mockImplementation(async () => { current = false; return assertion; });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.authenticate({ isCurrent: () => current }); });
    expect(mocks.post).toHaveBeenCalledTimes(1);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('rejects a pending ceremony if the session changes and changes back', async () => {
    mocks.getCredential.mockImplementation(async () => {
      window.dispatchEvent(new CustomEvent('authStateChanged'));
      return assertion;
    });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.authenticate(); });
    expect(mocks.post).toHaveBeenCalledTimes(1);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('does not install a session if auth changes while finish is pending', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } }).mockImplementationOnce(async () => {
      window.dispatchEvent(new CustomEvent('authStateChanged'));
      return { data: session };
    });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.authenticate(); });
    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('reports discoverable login rate limiting', async () => {
    mocks.post.mockReset().mockRejectedValueOnce({ response: { status: 429 } });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.authenticate(); });
    expect(result.current.error).toBe('authentication_rate_limited');
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('reports discoverable login infrastructure failures', async () => {
    mocks.post.mockReset().mockRejectedValueOnce({ response: { status: 503 } });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.authenticate(); });
    expect(result.current.error).toBe('authentication_unavailable');
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('rejects a malformed response without replacing the prior session', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } }).mockResolvedValueOnce({ data: { access_token: '' } });
    const { result } = renderHook(() => useWebAuthn());
    let returned: unknown;
    await act(async () => { returned = await result.current.authenticate({ patientId: '7' }); });
    expect(returned).toBeNull();
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
    expect(result.current.error).toBe('authentication_failed');
  });

  it.each([
    { ...session, token_type: 'unsupported' },
    { ...session, user: { ...patient, role: 'Admin' } },
    { ...session, user: { ...patient, is_superuser: true } },
    { ...session, user: { ...patient, is_active: false } },
  ])('rejects an invalid principal or token type without installing it', async (badSession) => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } }).mockResolvedValueOnce({ data: badSession });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.authenticate({ patientId: '7' }); });
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
    expect(result.current.error).toBe('authentication_failed');
  });

  it('does not replace a newer session while the browser ceremony is in flight', async () => {
    mocks.getAccessToken.mockReturnValueOnce('prior-staff-token').mockReturnValueOnce('new-session-token');
    const { result } = renderHook(() => useWebAuthn());
    let returned: unknown;
    await act(async () => { returned = await result.current.authenticate({ patientId: '7' }); });
    expect(returned).toBeNull();
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
    expect(result.current.error).toBe('authentication_failed');
  });

  it('requires a ceremony identifier before invoking the authenticator', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options: { ...options, ceremony_id: '' } } });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.authenticate({ patientId: '7' }); });
    expect(mocks.getCredential).not.toHaveBeenCalled();
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
    expect(result.current.error).toBe('authentication_failed');
  });
});


describe('passkey management', () => {
  const creationOptions = {
    challenge: 'AA', ceremony_id: 'ceremony', rp: { id: 'clinic.example', name: 'Clinic' },
    user: { id: 'AQ', name: 'synthetic', displayName: 'Synthetic' },
    pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
    authenticatorSelection: { userVerification: 'required' },
  };
  const attestation = { id: 'AQ', rawId: new Uint8Array([1]).buffer, type: 'public-key',
    response: { attestationObject: new Uint8Array([2]).buffer, clientDataJSON: new Uint8Array([3]).buffer } };
  const stepUp = { phone: '+998900000000', verification_grant: 'synthetic-grant' };

  it('uses a fresh grant and ceremony with the canonical session', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options: creationOptions } }).mockResolvedValueOnce({ data: {} });
    mocks.createCredential.mockResolvedValue(attestation);
    const { result } = renderHook(() => useWebAuthn());
    let success = false;
    await act(async () => { success = await result.current.register({ ...stepUp, name: 'Device' }); });
    expect(success).toBe(true);
    expect(mocks.post).toHaveBeenNthCalledWith(1, '/webauthn/register/begin', { ...stepUp, credential_name: 'Device' });
    expect(mocks.createCredential).toHaveBeenCalledWith({ publicKey: expect.objectContaining({ authenticatorSelection: { userVerification: 'required' }, challenge: new Uint8Array([0]).buffer }) });
    expect(mocks.post).toHaveBeenNthCalledWith(2, '/webauthn/register/finish', { ceremony_id: 'ceremony', credential_name: 'Device', credential_response: expect.objectContaining({ id: 'AQ' }) });
  });

  it('does not start a browser ceremony after auth changes during registration begin', async () => {
    mocks.post.mockReset().mockImplementationOnce(async () => {
      window.dispatchEvent(new CustomEvent('authStateChanged'));
      return { data: { options: creationOptions } };
    });
    const { result } = renderHook(() => useWebAuthn());
    let success = true;
    await act(async () => { success = await result.current.register({ ...stepUp, name: 'Device' }); });
    expect(success).toBe(false);
    expect(mocks.createCredential).not.toHaveBeenCalled();
  });

  it('does not report success if auth changes during registration finish', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options: creationOptions } }).mockImplementationOnce(async () => {
      window.dispatchEvent(new CustomEvent('authStateChanged'));
      return { data: {} };
    });
    mocks.createCredential.mockResolvedValue(attestation);
    const { result } = renderHook(() => useWebAuthn());
    let success = true;
    await act(async () => { success = await result.current.register({ ...stepUp, name: 'Device' }); });
    expect(success).toBe(false);
  });

  it('does not report deactivation success after an auth change', async () => {
    mocks.post.mockReset().mockImplementationOnce(async () => {
      window.dispatchEvent(new CustomEvent('authStateChanged'));
      return { data: {} };
    });
    const { result } = renderHook(() => useWebAuthn());
    let success = true;
    await act(async () => { success = await result.current.deactivateCredential(123, stepUp); });
    expect(success).toBe(false);
  });

  it('does not finish a ceremony after the patient session changes', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options: creationOptions } });
    mocks.createCredential.mockImplementation(async () => { mocks.getAccessToken.mockReturnValue('new-token'); return attestation; });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.register({ ...stepUp, name: 'Device' }); });
    expect(mocks.post).toHaveBeenCalledTimes(1);
    expect(result.current.error).toBe('registration_failed');
  });

  it('explains when the last passkey cannot be removed', async () => {
    mocks.post.mockReset().mockRejectedValueOnce({ response: { status: 409, data: { detail: { reason: 'last_active_credential' } } } });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.deactivateCredential(123, stepUp); });
    expect(result.current.error).toBe('last_active_credential');
  });

  it('reports service unavailability when deactivation fails', async () => {
    mocks.post.mockReset().mockRejectedValueOnce({ response: { status: 503 } });
    const { result } = renderHook(() => useWebAuthn());
    let success = true;
    await act(async () => { success = await result.current.deactivateCredential(123, stepUp); });
    expect(success).toBe(false);
    expect(mocks.post).toHaveBeenCalledWith('/webauthn/credentials/123/deactivate', stepUp);
    expect(result.current.error).toBe('management_unavailable');
  });
});
