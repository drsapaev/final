import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  post: vi.fn(),
  ensureCSRFToken: vi.fn(),
  replaceAccessOnlySession: vi.fn(),
  getAccessToken: vi.fn(),
  getCredential: vi.fn(),
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
    value: { get: mocks.getCredential },
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
