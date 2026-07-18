/**
 * useWebAuthn — P5 frontend integration for passkey registration/login.
 *
 * Uses Web Authentication API (navigator.credentials) to register
 * and authenticate with passkeys. Requires HTTPS (or localhost).
 */
import { useCallback, useState } from 'react';
import { api } from '../api/client';

function base64urlToBuffer(base64url: string): ArrayBuffer {
  const padding = '='.repeat((4 - (base64url.length % 4)) % 4);
  const base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(base64);
  const buffer = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    buffer[i] = binary.charCodeAt(i);
  }
  return buffer.buffer;
}

function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

interface RegisterOptions {
  name?: string;
  rpId?: string;
  rpName?: string;
}

interface AuthenticateOptions {
  patientId: string;
  rpId?: string;
}

interface AuthResponseData {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  [key: string]: unknown;
}

interface WebAuthnErrorResponse {
  response?: {
    data?: {
      detail?: {
        reason?: string;
      };
    };
  };
}

export interface UseWebAuthnReturn {
  isSupported: boolean;
  isRegistering: boolean;
  isAuthenticating: boolean;
  error: string;
  register: (options?: RegisterOptions) => Promise<boolean>;
  authenticate: (options: AuthenticateOptions) => Promise<AuthResponseData | null>;
  listCredentials: () => Promise<unknown[]>;
  deactivateCredential: (credentialId: string) => Promise<boolean>;
}

export function useWebAuthn(): UseWebAuthnReturn {
  const [isRegistering, setIsRegistering] = useState<boolean>(false);
  const [isAuthenticating, setIsAuthenticating] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  const isSupported =
    typeof window !== 'undefined' && typeof window.PublicKeyCredential !== 'undefined';

  const register = useCallback(
    async (options: RegisterOptions = {}): Promise<boolean> => {
      if (!isSupported) {
        setError('webauthn_not_supported');
        return false;
      }

      setIsRegistering(true);
      setError('');

      try {
        const token = sessionStorage.getItem('patient_jwt_token');
        if (!token) {
          setError('not_authenticated');
          return false;
        }

        const beginResponse = await api.post('/webauthn/register/begin', {
          credential_name: options.name,
          rp_id: options.rpId || window.location.hostname,
          rp_name: options.rpName || 'Medical Clinic',
        });

        const optionsData = beginResponse.data as {
          options: {
            challenge: string;
            rp: { id: string; name: string };
            user: { id: string; name: string; displayName: string };
            pubKeyCredParams?: Array<{ type: string; alg: number }>;
            timeout?: number;
          };
        };

        const publicKeyOptions: PublicKeyCredentialCreationOptions = {
          challenge: base64urlToBuffer(optionsData.options.challenge),
          rp: {
            id: optionsData.options.rp.id,
            name: optionsData.options.rp.name,
          },
          user: {
            id: base64urlToBuffer(optionsData.options.user.id),
            name: optionsData.options.user.name,
            displayName: optionsData.options.user.displayName,
          },
          pubKeyCredParams: (optionsData.options.pubKeyCredParams || [
            { type: 'public-key' as const, alg: -7 },
          ]) as PublicKeyCredentialParameters[],
          timeout: optionsData.options.timeout || 60000,
          attestation: 'none' as AttestationConveyancePreference,
        };

        const credential = (await navigator.credentials.create({
          publicKey: publicKeyOptions,
        })) as PublicKeyCredential | null;

        if (!credential) {
          setError('registration_cancelled');
          return false;
        }

        const attestationResponse = credential.response as AuthenticatorAttestationResponse;
        const credentialResponse = {
          id: credential.id,
          rawId: bufferToBase64url(credential.rawId),
          type: credential.type,
          response: {
            attestationObject: bufferToBase64url(attestationResponse.attestationObject),
            clientDataJSON: bufferToBase64url(attestationResponse.clientDataJSON),
          },
        };

        await api.post('/webauthn/register/finish', {
          credential_response: credentialResponse,
          rp_id: options.rpId || window.location.hostname,
          origin: window.location.origin,
          credential_name: options.name,
        });

        return true;
      } catch (err) {
        const e = err as WebAuthnErrorResponse;
        setError(e?.response?.data?.detail?.reason || 'registration_failed');
        return false;
      } finally {
        setIsRegistering(false);
      }
    },
    [isSupported],
  );

  const authenticate = useCallback(
    async (options: AuthenticateOptions): Promise<AuthResponseData | null> => {
      if (!isSupported) {
        setError('webauthn_not_supported');
        return null;
      }

      setIsAuthenticating(true);
      setError('');

      try {
        const beginResponse = await api.post('/webauthn/login/begin', {
          patient_id: options.patientId,
          rp_id: options.rpId || window.location.hostname,
        });

        const optionsData = beginResponse.data as {
          options: {
            challenge: string;
            rpId: string;
            timeout?: number;
          };
        };

        const publicKeyOptions: PublicKeyCredentialRequestOptions = {
          challenge: base64urlToBuffer(optionsData.options.challenge),
          rpId: optionsData.options.rpId,
          timeout: optionsData.options.timeout || 60000,
          userVerification: 'preferred' as UserVerificationRequirement,
        };

        const assertion = (await navigator.credentials.get({
          publicKey: publicKeyOptions,
        })) as PublicKeyCredential | null;

        if (!assertion) {
          setError('authentication_cancelled');
          return null;
        }

        const assertionResponse = assertion.response as AuthenticatorAssertionResponse;
        const assertionData = {
          id: assertion.id,
          rawId: bufferToBase64url(assertion.rawId),
          type: assertion.type,
          response: {
            authenticatorData: bufferToBase64url(assertionResponse.authenticatorData),
            clientDataJSON: bufferToBase64url(assertionResponse.clientDataJSON),
            signature: bufferToBase64url(assertionResponse.signature),
            userHandle: assertionResponse.userHandle
              ? bufferToBase64url(assertionResponse.userHandle)
              : null,
          },
        };

        const finishResponse = await api.post('/webauthn/login/finish', {
          patient_id: options.patientId,
          assertion_response: assertionData,
          rp_id: options.rpId || window.location.hostname,
          origin: window.location.origin,
        });

        const data = finishResponse.data as AuthResponseData | undefined;
        if (data?.access_token) {
          sessionStorage.setItem('patient_jwt_token', data.access_token);
          sessionStorage.setItem('patient_refresh_token', data.refresh_token);
          sessionStorage.setItem(
            'patient_token_expires_at',
            String(Date.now() + data.expires_in * 1000),
          );
        }

        return data ?? null;
      } catch (err) {
        const e = err as WebAuthnErrorResponse;
        setError(e?.response?.data?.detail?.reason || 'authentication_failed');
        return null;
      } finally {
        setIsAuthenticating(false);
      }
    },
    [isSupported],
  );

  const listCredentials = useCallback(async (): Promise<unknown[]> => {
    try {
      const response = await api.post('/webauthn/credentials/list', {});
      return (response.data as { credentials?: unknown[] })?.credentials || [];
    } catch {
      return [];
    }
  }, []);

  const deactivateCredential = useCallback(
    async (credentialId: string): Promise<boolean> => {
      try {
        await api.post(`/webauthn/credentials/${credentialId}/deactivate`, {});
        return true;
      } catch {
        return false;
      }
    },
    [],
  );

  return {
    isSupported,
    isRegistering,
    isAuthenticating,
    error,
    register,
    authenticate,
    listCredentials,
    deactivateCredential,
  };
}

export default useWebAuthn;
