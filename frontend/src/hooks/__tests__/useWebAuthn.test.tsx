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
const nextOptions = {
  challenge: 'AQID', rpId: 'clinic.example', ceremony_id: 'synthetic-confirm-ceremony',
  timeout: 45000, userVerification: 'required',
  allowCredentials: [{ type: 'public-key', id: 'AQI' }],
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
  mocks.post.mockReset();
  mocks.getCredential.mockReset();
  mocks.getAccessToken.mockReset();
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
    expect(mocks.getCredential).toHaveBeenCalledWith(expect.objectContaining({
      publicKey: expect.objectContaining({
        rpId: 'clinic.example',
        challenge: new Uint8Array([0, 1, 254, 255]).buffer,
      }),
      signal: expect.any(AbortSignal),
    }));
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

  it.each([false, true])('returns a pending TOTP challenge after passkey, discoverable=%s', async (discoverable) => {
    const pending = { requires_2fa: true, two_factor_method: 'totp', pending_2fa_token: 'pending', user: patient };
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } });
    if (discoverable) mocks.post.mockResolvedValueOnce({ data: { next_options: nextOptions } });
    mocks.post.mockResolvedValueOnce({ data: pending });
    const { result } = renderHook(() => useWebAuthn());
    let returned: unknown;
    if (discoverable) {
      let task!: Promise<unknown>;
      await act(async () => { task = result.current.authenticate(); });
      expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
      await act(async () => { result.current.confirmAuthentication(); returned = await task; });
    } else {
      await act(async () => { returned = await result.current.authenticate({ patientId: '7' }); });
    }
    expect(returned).toEqual(pending);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('confirms the same discoverable key twice before installing a patient session', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } })
      .mockResolvedValueOnce({ data: { next_options: nextOptions } })
      .mockResolvedValueOnce({ data: session });
    mocks.getCredential.mockImplementation(async () => {
      expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
      return assertion;
    });
    const { result } = renderHook(() => useWebAuthn());
    let returned: unknown;
    let task!: Promise<unknown>;
    await act(async () => { task = result.current.authenticate(); });
    expect(result.current.authenticationStep).toBe('confirm');
    expect(mocks.getCredential).toHaveBeenCalledTimes(1);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
    await act(async () => { result.current.confirmAuthentication(); returned = await task; });
    expect(mocks.post).toHaveBeenNthCalledWith(1, '/webauthn/login/discoverable/begin', {});
    expect(mocks.post).toHaveBeenNthCalledWith(2, '/webauthn/login/discoverable/finish', {
      ceremony_id: 'synthetic-ceremony-id', assertion_response: expect.objectContaining({ id: 'AQI' }),
    });
    expect(mocks.getCredential).toHaveBeenCalledTimes(2);
    expect(mocks.getCredential).toHaveBeenNthCalledWith(2, expect.objectContaining({
      publicKey: expect.objectContaining({
        challenge: new Uint8Array([1, 2, 3]).buffer,
        rpId: 'clinic.example', userVerification: 'required', timeout: 45000,
        allowCredentials: [{ type: 'public-key', id: new Uint8Array([1, 2]).buffer }],
      }),
      signal: expect.any(AbortSignal),
    }));
    expect(mocks.post).toHaveBeenNthCalledWith(3, '/webauthn/login/discoverable/complete', {
      ceremony_id: 'synthetic-confirm-ceremony', assertion_response: expect.objectContaining({ id: 'AQI', rawId: 'AQI' }),
    });
    expect(returned).toMatchObject({ access_token: 'patient-access' });
    expect(mocks.replaceAccessOnlySession).toHaveBeenCalledWith('patient-access', patient);
  });

  it('exposes confirmation state without installing a session while the second prompt is pending', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } })
      .mockResolvedValueOnce({ data: { next_options: nextOptions } })
      .mockResolvedValueOnce({ data: session });
    let resolveSecond!: (value: typeof assertion) => void;
    mocks.getCredential.mockResolvedValueOnce(assertion).mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve; }));
    const { result } = renderHook(() => useWebAuthn());
    let task!: Promise<unknown>;
    await act(async () => { task = result.current.authenticate(); });
    expect(result.current.authenticationStep).toBe('confirm');
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(mocks.getCredential).toHaveBeenCalledTimes(1);
    act(() => {
      result.current.confirmAuthentication();
      // A fresh WebAuthn call must start synchronously in the click handler.
      expect(mocks.getCredential).toHaveBeenCalledTimes(2);
    });
    expect(result.current.authenticationStep).toBe('confirming');
    await act(async () => { resolveSecond(assertion); await task; });
    expect(result.current.authenticationStep).toBeNull();
    expect(mocks.replaceAccessOnlySession).toHaveBeenCalledTimes(1);
  });

  it.each([
    { ...nextOptions, challenge: '' },
    { ...nextOptions, challenge: '!!' },
    { ...nextOptions, ceremony_id: '' },
    { ...nextOptions, rpId: 'other.example' },
    { ...nextOptions, userVerification: 'preferred' },
    { ...nextOptions, allowCredentials: [] },
    { ...nextOptions, allowCredentials: [{ type: 'public-key', id: 'Aw' }] },
    { ...nextOptions, allowCredentials: [{ type: 'other', id: 'AQI' }] },
    { ...nextOptions, allowCredentials: [{ type: 'public-key', id: 'AQI' }, { type: 'public-key', id: 'AQI' }] },
  ])('rejects malformed or mismatched second options before the second prompt', async (invalidOptions) => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } })
      .mockResolvedValueOnce({ data: { next_options: invalidOptions } });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.authenticate(); });
    expect(mocks.getCredential).toHaveBeenCalledTimes(1);
    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
    expect(result.current.error).toBe('authentication_failed');
  });

  it('rejects a session returned prematurely by the first assertion', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } })
      .mockResolvedValueOnce({ data: { ...session, next_options: nextOptions } });
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => { await result.current.authenticate(); });
    expect(mocks.getCredential).toHaveBeenCalledTimes(1);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
    expect(result.current.error).toBe('authentication_failed');
  });

  it('does not install a session when the second prompt is cancelled', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } }).mockResolvedValueOnce({ data: { next_options: nextOptions } });
    mocks.getCredential.mockResolvedValueOnce(assertion).mockRejectedValueOnce(new DOMException('cancelled', 'NotAllowedError'));
    const { result } = renderHook(() => useWebAuthn());
    let task!: Promise<unknown>;
    await act(async () => { task = result.current.authenticate(); });
    await act(async () => { result.current.confirmAuthentication(); await task; });
    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
    expect(result.current.error).toBe('authentication_cancelled');
  });

  it.each([
    { response: { status: 403 } },
    { response: { status: 429 } },
    { response: { status: 503 } },
    new Error('synthetic network failure'),
  ])('does not install a session if completion fails or is replayed', async (failure) => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } })
      .mockResolvedValueOnce({ data: { next_options: nextOptions } }).mockRejectedValueOnce(failure);
    const { result } = renderHook(() => useWebAuthn());
    let task!: Promise<unknown>;
    await act(async () => { task = result.current.authenticate(); });
    await act(async () => { result.current.confirmAuthentication(); await task; });
    expect(mocks.post).toHaveBeenCalledTimes(3);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('aborts a pending second prompt after auth changes and does not complete', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } }).mockResolvedValueOnce({ data: { next_options: nextOptions } });
    mocks.getCredential.mockResolvedValueOnce(assertion).mockImplementationOnce(async ({ signal }: { signal: AbortSignal }) => {
      window.dispatchEvent(new Event('authStateChanged'));
      expect(signal.aborted).toBe(true);
      return assertion;
    });
    const { result } = renderHook(() => useWebAuthn());
    let task!: Promise<unknown>;
    await act(async () => { task = result.current.authenticate(); });
    await act(async () => { result.current.confirmAuthentication(); await task; });
    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('discards completion if auth changes while the final response is pending', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } })
      .mockResolvedValueOnce({ data: { next_options: nextOptions } })
      .mockImplementationOnce(async () => { window.dispatchEvent(new Event('authStateChanged')); return { data: session }; });
    const { result } = renderHook(() => useWebAuthn());
    let task!: Promise<unknown>;
    await act(async () => { task = result.current.authenticate(); });
    await act(async () => { result.current.confirmAuthentication(); await task; });
    expect(mocks.post).toHaveBeenCalledTimes(3);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('cancels the waiting confirmation on auth change before the user clicks', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } }).mockResolvedValueOnce({ data: { next_options: nextOptions } });
    const { result } = renderHook(() => useWebAuthn());
    let task!: Promise<unknown>;
    await act(async () => { task = result.current.authenticate(); });
    expect(result.current.authenticationStep).toBe('confirm');
    await act(async () => { window.dispatchEvent(new Event('authStateChanged')); await task; });
    expect(mocks.getCredential).toHaveBeenCalledTimes(1);
    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('aborts the second prompt when the hook is unmounted', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } }).mockResolvedValueOnce({ data: { next_options: nextOptions } });
    let resolveSecond!: (value: typeof assertion) => void;
    let secondSignal!: AbortSignal;
    mocks.getCredential.mockResolvedValueOnce(assertion).mockImplementationOnce(({ signal }: { signal: AbortSignal }) => {
      secondSignal = signal;
      return new Promise((resolve) => { resolveSecond = resolve; });
    });
    const { result, unmount } = renderHook(() => useWebAuthn());
    let task!: Promise<unknown>;
    await act(async () => { task = result.current.authenticate(); });
    await act(async () => { result.current.confirmAuthentication(); });
    unmount();
    expect(secondSignal.aborted).toBe(true);
    await act(async () => { resolveSecond(assertion); await task; });
    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
  });

  it('aborts an older attempt when a newer login starts', async () => {
    mocks.post.mockReset().mockImplementation(async (url) => {
      if (url === '/webauthn/login/discoverable/begin') return { data: { options } };
      if (url === '/webauthn/login/discoverable/finish') return { data: { next_options: nextOptions } };
      if (url === '/webauthn/login/discoverable/complete') return { data: session };
      throw new Error('Unexpected endpoint');
    });
    let resolveOld!: (value: typeof assertion) => void;
    let oldSignal!: AbortSignal;
    mocks.getCredential.mockImplementationOnce(({ signal }: { signal: AbortSignal }) => {
      oldSignal = signal;
      return new Promise((resolve) => { resolveOld = resolve; });
    }).mockResolvedValue(assertion);
    const { result } = renderHook(() => useWebAuthn());
    let oldTask!: Promise<unknown>;
    await act(async () => { oldTask = result.current.authenticate(); });
    let newTask!: Promise<unknown>;
    await act(async () => { newTask = result.current.authenticate(); });
    await act(async () => { result.current.confirmAuthentication(); await newTask; });
    expect(oldSignal.aborted).toBe(true);
    expect(mocks.replaceAccessOnlySession).toHaveBeenCalledTimes(1);
    await act(async () => { resolveOld(assertion); await oldTask; });
    expect(mocks.replaceAccessOnlySession).toHaveBeenCalledTimes(1);
    expect(mocks.post.mock.calls.filter(([url]) => url === '/webauthn/login/discoverable/complete')).toHaveLength(1);
  });

  it('allows cancelling before the second prompt without creating a session', async () => {
    mocks.post.mockReset().mockResolvedValueOnce({ data: { options } }).mockResolvedValueOnce({ data: { next_options: nextOptions } });
    const { result } = renderHook(() => useWebAuthn());
    let task!: Promise<unknown>;
    await act(async () => { task = result.current.authenticate(); });
    expect(result.current.authenticationStep).toBe('confirm');
    await act(async () => { result.current.cancelAuthentication(); await task; });
    expect(result.current.error).toBe('authentication_cancelled');
    expect(mocks.getCredential).toHaveBeenCalledTimes(1);
    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(mocks.replaceAccessOnlySession).not.toHaveBeenCalled();
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
    expect(result.current.error).toBe('');
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
