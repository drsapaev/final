/**
 * useWebAuthn — P5 frontend integration for passkey registration/login.
 *
 * Uses Web Authentication API (navigator.credentials) to register
 * and authenticate with passkeys. Requires HTTPS (or localhost).
 */
import { useCallback, useState } from 'react';
import { api, ensureCSRFToken } from '../api/client';
import { mapPatientSession } from '../api/mappers/patientAccess';
import { replaceAccessOnlySession } from '../stores/auth';
import type { PatientSession } from '../types/domain/patientAccess';
import type { HttpApiError } from '../types/errors';
import { tokenManager } from '../utils/tokenManager';

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

export interface UseWebAuthnReturn {
  isSupported: boolean;
  isRegistering: boolean;
  isAuthenticating: boolean;
  error: string;
  register: (options?: RegisterOptions) => Promise<boolean>;
  authenticate: (options: AuthenticateOptions) => Promise<PatientSession | null>;
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
        const e = err as HttpApiError;
        const detail = e?.response?.data?.detail;
        const reason = typeof detail === 'object' && detail ? detail.reason : undefined;
        setError(reason || 'registration_failed');
        return false;
      } finally {
        setIsRegistering(false);
      }
    },
    [isSupported],
  );

  const authenticate = useCallback(
    async (options: AuthenticateOptions): Promise<PatientSession | null> => {
      if (!isSupported) {
        setError('webauthn_not_supported');
        return null;
      }

      setIsAuthenticating(true);
      setError('');
      // A pending browser ceremony must not replace a newer login in this tab.
      const originalToken = tokenManager.getAccessToken();

      try {
        const beginResponse = await api.post('/webauthn/login/begin', {
          patient_id: options.patientId,
        });

        const optionsData = beginResponse.data as {
          options: {
            challenge: string;
            rpId: string;
            ceremony_id: string;
            timeout?: number;
          };
        };
        if (
          !optionsData?.options ||
          typeof optionsData.options.challenge !== 'string' ||
          !optionsData.options.challenge ||
          typeof optionsData.options.rpId !== 'string' ||
          !optionsData.options.rpId ||
          typeof optionsData.options.ceremony_id !== 'string' ||
          !optionsData.options.ceremony_id
        ) {
          throw new Error('Invalid passkey authentication options');
        }

        const publicKeyOptions: PublicKeyCredentialRequestOptions = {
          challenge: base64urlToBuffer(optionsData.options.challenge),
          rpId: optionsData.options.rpId,
          timeout: optionsData.options.timeout || 60000,
          userVerification: 'required' as UserVerificationRequirement,
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
          ceremony_id: optionsData.options.ceremony_id,
          assertion_response: assertionData,
        });

        const session = mapPatientSession(finishResponse.data);
        const accessToken = session.access_token.trim();
        if (
          !accessToken ||
          session.token_type.toLowerCase() !== 'bearer' ||
          session.user.role.toLowerCase() !== 'patient' ||
          !session.user.is_active ||
          session.user.is_superuser ||
          tokenManager.getAccessToken() !== originalToken
        ) {
          throw new Error('Invalid or superseded patient session');
        }

        // Remove any prior staff refresh token before installing the new
        // access-only patient principal, exactly like patient OTP login.
        const profile: Record<string, unknown> = session.user;
        replaceAccessOnlySession(accessToken, profile);
        void ensureCSRFToken().catch(() => {
          // The interceptor retries CSRF initialization on demand.
        });
        return { ...session, access_token: accessToken };
      } catch (err) {
        const e = err as HttpApiError;
        const detail = e?.response?.data?.detail;
        const reason = typeof detail === 'object' && detail ? detail.reason : undefined;
        setError(reason || 'authentication_failed');
        return null;
      } finally {
        setIsAuthenticating(false);
      }
    },
    [isSupported],
  );

  const listCredentials = useCallback(async (): Promise<unknown[]> => {
    const response = await api.post('/webauthn/credentials/list', {});
    const credentials = (response.data as { credentials?: unknown } | null)?.credentials;
    if (!Array.isArray(credentials) || credentials.some((item: unknown) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) return true;
      const entry = item as Record<string, unknown>;
      return (typeof entry.id !== 'number' && typeof entry.id !== 'string') ||
        ['name', 'device_type', 'last_used_at'].some((key) =>
          entry[key] !== null && entry[key] !== undefined && typeof entry[key] !== 'string');
    })) {
      throw new Error('Invalid passkey list response');
    }
    return credentials;
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
