/**
 * useWebAuthn — P5 frontend integration for passkey registration/login.
 *
 * Uses Web Authentication API (navigator.credentials) to register
 * and authenticate with passkeys. Requires HTTPS (or localhost).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ensureCSRFToken } from '../api/client';
import { mapPatientLoginResult } from '../api/mappers/patientAccess';
import { replaceAccessOnlySession } from '../stores/auth';
import { isPatientPendingTwoFactor } from '../types/domain/patientAccess';
import type { PatientLoginResult } from '../types/domain/patientAccess';
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

function requiredBase64url(value: unknown): ArrayBuffer {
  if (typeof value !== 'string' || value.length === 0 || value.length > 2048 || !/^[A-Za-z0-9_-]+$/.test(value)) {
    throw new Error('Invalid WebAuthn value');
  }
  const decoded = base64urlToBuffer(value);
  if (decoded.byteLength === 0 || bufferToBase64url(decoded) !== value) throw new Error('Invalid WebAuthn value');
  return decoded;
}

function serializeAssertion(assertion: PublicKeyCredential) {
  const response = assertion.response as AuthenticatorAssertionResponse;
  return {
    id: assertion.id,
    rawId: bufferToBase64url(assertion.rawId),
    type: assertion.type,
    response: {
      authenticatorData: bufferToBase64url(response.authenticatorData),
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      signature: bufferToBase64url(response.signature),
      userHandle: response.userHandle ? bufferToBase64url(response.userHandle) : null,
    },
  };
}

interface StepUp {
  phone: string;
  verification_grant: string;
}

interface RegisterOptions extends StepUp {
  name: string;
}

interface AuthenticateOptions {
  patientId?: string;
  isCurrent?: () => boolean;
}

export interface UseWebAuthnReturn {
  isSupported: boolean;
  isRegistering: boolean;
  isAuthenticating: boolean;
  authenticationStep: 'select' | 'confirm' | 'confirming' | null;
  error: string;
  register: (options: RegisterOptions) => Promise<boolean>;
  authenticate: (options?: AuthenticateOptions) => Promise<PatientLoginResult | null>;
  confirmAuthentication: () => void;
  cancelAuthentication: () => void;
  listCredentials: () => Promise<unknown[]>;
  deactivateCredential: (credentialId: string | number, stepUp: StepUp) => Promise<boolean>;
}

export function useWebAuthn(): UseWebAuthnReturn {
  const [isRegistering, setIsRegistering] = useState<boolean>(false);
  const [isAuthenticating, setIsAuthenticating] = useState<boolean>(false);
  const [authenticationStep, setAuthenticationStep] = useState<'select' | 'confirm' | 'confirming' | null>(null);
  const [error, setError] = useState<string>('');
  const mounted = useRef(true);
  const authenticationGeneration = useRef(0);
  const authenticationAbort = useRef<AbortController | null>(null);
  const confirmationControl = useRef<{ generation: number; start: () => void } | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      authenticationGeneration.current += 1;
      authenticationAbort.current?.abort();
      authenticationAbort.current = null;
      confirmationControl.current = null;
    };
  }, []);

  const isSupported =
    typeof window !== 'undefined' && typeof window.PublicKeyCredential !== 'undefined';

  const register = useCallback(
    async (options: RegisterOptions): Promise<boolean> => {
      if (!isSupported) {
        setError('webauthn_not_supported');
        return false;
      }

      setIsRegistering(true);
      setError('');
      const token = tokenManager.getAccessToken();
      let sessionChanged = false;
      const onAuthChange = () => { sessionChanged = true; };
      window.addEventListener('authStateChanged', onAuthChange);
      const sessionIsCurrent = () => !sessionChanged && tokenManager.getAccessToken() === token;

      try {
        if (!token) {
          setError('not_authenticated');
          return false;
        }

        const beginResponse = await api.post('/webauthn/register/begin', {
          phone: options.phone,
          verification_grant: options.verification_grant,
          credential_name: options.name,
        });

        const optionsData = beginResponse.data as {
          options: {
            challenge: string;
            rp: { id: string; name: string };
            user: { id: string; name: string; displayName: string };
            pubKeyCredParams?: Array<{ type: string; alg: number }>;
            timeout?: number;
            ceremony_id: string;
            authenticatorSelection?: AuthenticatorSelectionCriteria;
            attestation?: AttestationConveyancePreference;
            excludeCredentials?: Array<{ id: string; type: PublicKeyCredentialType; transports?: AuthenticatorTransport[] }>;
          };
        };
        if (!optionsData?.options?.ceremony_id || !optionsData.options.challenge ||
            !optionsData.options.user?.id || !optionsData.options.rp?.id ||
            !sessionIsCurrent()) {
          throw new Error('Invalid or superseded registration ceremony');
        }

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
          authenticatorSelection: optionsData.options.authenticatorSelection,
          attestation: optionsData.options.attestation,
          excludeCredentials: optionsData.options.excludeCredentials?.map((item) => ({
            ...item, id: base64urlToBuffer(item.id),
          })),
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

        if (!sessionIsCurrent()) {
          throw new Error('Superseded registration ceremony');
        }
        await api.post('/webauthn/register/finish', {
          ceremony_id: optionsData.options.ceremony_id,
          credential_response: credentialResponse,
          credential_name: options.name,
        });

        return sessionIsCurrent();
      } catch (err) {
        const e = err as HttpApiError;
        const detail = e?.response?.data?.detail;
        const reason = typeof detail === 'object' && detail ? detail.reason : undefined;
        setError(e?.response?.status === 503 ? 'management_unavailable' :
          reason === 'step_up_failed' || reason === 'step_up_required' ? 'step_up_failed' : 'registration_failed');
        return false;
      } finally {
        window.removeEventListener('authStateChanged', onAuthChange);
        setIsRegistering(false);
      }
    },
    [isSupported],
  );

  const authenticate = useCallback(
    async (options: AuthenticateOptions = {}): Promise<PatientLoginResult | null> => {
      if (!isSupported) {
        setError('webauthn_not_supported');
        return null;
      }

      authenticationAbort.current?.abort();
      const controller = new AbortController();
      authenticationAbort.current = controller;
      const generation = ++authenticationGeneration.current;
      setIsAuthenticating(true);
      setAuthenticationStep('select');
      setError('');
      // A pending browser ceremony must not replace a newer login in this tab.
      const originalToken = tokenManager.getAccessToken();
      let sessionChanged = false;
      const onAuthChange = () => { sessionChanged = true; controller.abort(); };
      window.addEventListener('authStateChanged', onAuthChange);
      const sessionIsCurrent = () => {
        if (!mounted.current || generation !== authenticationGeneration.current || controller.signal.aborted || sessionChanged) return false;
        if (tokenManager.getAccessToken() !== originalToken || (options.isCurrent && !options.isCurrent())) {
          sessionChanged = true;
          controller.abort();
          return false;
        }
        return true;
      };

      try {
        const discoverable = !options.patientId;
        const beginResponse = await api.post(
          discoverable ? '/webauthn/login/discoverable/begin' : '/webauthn/login/begin',
          discoverable ? {} : { patient_id: options.patientId },
        );

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
          !optionsData.options.ceremony_id ||
          !sessionIsCurrent()
        ) {
          throw new Error('Invalid passkey authentication options');
        }

        const publicKeyOptions: PublicKeyCredentialRequestOptions = {
          challenge: requiredBase64url(optionsData.options.challenge),
          rpId: optionsData.options.rpId,
          timeout: optionsData.options.timeout || 60000,
          userVerification: 'required' as UserVerificationRequirement,
        };

        const assertion = (await navigator.credentials.get({
          publicKey: publicKeyOptions,
          signal: controller.signal,
        })) as PublicKeyCredential | null;

        if (!assertion) {
          if (sessionIsCurrent()) setError('authentication_cancelled');
          return null;
        }

        const assertionData = serializeAssertion(assertion);

        if (!sessionIsCurrent()) {
          throw new Error('Superseded authentication ceremony');
        }
        const finishResponse = await api.post(
          discoverable ? '/webauthn/login/discoverable/finish' : '/webauthn/login/finish',
          {
            ...(!discoverable ? { patient_id: options.patientId } : {}),
            ceremony_id: optionsData.options.ceremony_id,
            assertion_response: assertionData,
          },
        );

        let sessionPayload = finishResponse.data;
        if (discoverable) {
          if (!sessionIsCurrent()) throw new Error('Superseded authentication ceremony');
          const firstResult = finishResponse.data as Record<string, unknown>;
          if (!firstResult || typeof firstResult !== 'object' ||
              'access_token' in firstResult || 'token_type' in firstResult || 'user' in firstResult) {
            throw new Error('Invalid first authentication result');
          }
          const next = firstResult.next_options as {
            challenge?: unknown; ceremony_id?: unknown; rpId?: unknown; timeout?: unknown;
            userVerification?: unknown; allowCredentials?: unknown;
          } | null;
          if (!next || typeof next !== 'object' || typeof next.ceremony_id !== 'string' || !next.ceremony_id ||
              typeof next.rpId !== 'string' || !next.rpId || next.rpId !== optionsData.options.rpId ||
              next.userVerification !== 'required' || !Array.isArray(next.allowCredentials) || next.allowCredentials.length !== 1) {
            throw new Error('Invalid second authentication options');
          }
          const allowed = next.allowCredentials[0] as { id?: unknown; type?: unknown } | null;
          if (!allowed || typeof allowed !== 'object' || allowed.type !== 'public-key') {
            throw new Error('Invalid allowed credential');
          }
          const allowedId = requiredBase64url(allowed.id);
          if (bufferToBase64url(allowedId) !== assertionData.rawId) throw new Error('Credential changed between ceremonies');
          const nextOptions: PublicKeyCredentialRequestOptions = {
            challenge: requiredBase64url(next.challenge),
            rpId: next.rpId,
            timeout: typeof next.timeout === 'number' && Number.isFinite(next.timeout) && next.timeout > 0 ? next.timeout : 60000,
            userVerification: 'required',
            allowCredentials: [{ type: 'public-key', id: allowedId }],
          };
          const confirmation = await new Promise<PublicKeyCredential | null>((resolve, reject) => {
            const onAbort = () => {
              if (confirmationControl.current?.generation === generation) confirmationControl.current = null;
              reject(new DOMException('Authentication cancelled', 'AbortError'));
            };
            if (!sessionIsCurrent()) { onAbort(); return; }
            controller.signal.addEventListener('abort', onAbort, { once: true });
            confirmationControl.current = {
              generation,
              start: () => {
                controller.signal.removeEventListener('abort', onAbort);
                if (!sessionIsCurrent()) { onAbort(); return; }
                // This call is synchronous in the user's click handler, so
                // browsers that require a fresh user activation can open it.
                try {
                  Promise.resolve(navigator.credentials.get({ publicKey: nextOptions, signal: controller.signal }))
                    .then((credential) => resolve(credential as PublicKeyCredential | null), reject);
                } catch (error) { reject(error); }
              },
            };
            setAuthenticationStep('confirm');
          });
          if (!confirmation) {
            if (sessionIsCurrent()) setError('authentication_cancelled');
            return null;
          }
          if (!sessionIsCurrent()) throw new Error('Superseded authentication ceremony');
          const confirmationData = serializeAssertion(confirmation);
          if (confirmationData.rawId !== assertionData.rawId) throw new Error('Credential changed between ceremonies');
          const completeResponse = await api.post('/webauthn/login/discoverable/complete', {
            ceremony_id: next.ceremony_id,
            assertion_response: confirmationData,
          });
          sessionPayload = completeResponse.data;
        }

        const session = mapPatientLoginResult(sessionPayload);
        if (isPatientPendingTwoFactor(session)) {
          if (!sessionIsCurrent()) throw new Error('Superseded authentication ceremony');
          return session;
        }
        const accessToken = session.access_token.trim();
        if (
          !accessToken ||
          session.token_type.toLowerCase() !== 'bearer' ||
          session.user.role.toLowerCase() !== 'patient' ||
          !session.user.is_active ||
          session.user.is_superuser ||
          !sessionIsCurrent()
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
        if (sessionIsCurrent()) setError(e?.response?.status === 503 ? 'authentication_unavailable' :
          e?.response?.status === 429 ? 'authentication_rate_limited' :
          (err instanceof DOMException && err.name === 'NotAllowedError') || reason === 'authentication_cancelled'
            ? 'authentication_cancelled' : 'authentication_failed');
        return null;
      } finally {
        window.removeEventListener('authStateChanged', onAuthChange);
        if (authenticationAbort.current === controller) authenticationAbort.current = null;
        if (confirmationControl.current?.generation === generation) confirmationControl.current = null;
        if (mounted.current && generation === authenticationGeneration.current) {
          setIsAuthenticating(false);
          setAuthenticationStep(null);
        }
      }
    },
    [isSupported],
  );

  const confirmAuthentication = useCallback(() => {
    const control = confirmationControl.current;
    if (!control || control.generation !== authenticationGeneration.current) return;
    confirmationControl.current = null;
    setAuthenticationStep('confirming');
    control.start();
  }, []);

  const cancelAuthentication = useCallback(() => {
    const controller = authenticationAbort.current;
    if (controller && !controller.signal.aborted) {
      setError('authentication_cancelled');
      controller.abort();
    }
  }, []);

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
    async (credentialId: string | number, stepUp: StepUp): Promise<boolean> => {
      setError('');
      const token = tokenManager.getAccessToken();
      let sessionChanged = false;
      const onAuthChange = () => { sessionChanged = true; };
      window.addEventListener('authStateChanged', onAuthChange);
      try {
        if (!token) { setError('not_authenticated'); return false; }
        await api.post(`/webauthn/credentials/${encodeURIComponent(String(credentialId))}/deactivate`, stepUp);
        return !sessionChanged && tokenManager.getAccessToken() === token;
      } catch (err) {
        const response = (err as HttpApiError)?.response;
        const detail = response?.data?.detail;
        const reason = typeof detail === 'object' && detail ? detail.reason : undefined;
        setError(response?.status === 503 ? 'management_unavailable' :
          reason === 'last_active_credential' ? 'last_active_credential' : 'deactivation_failed');
        return false;
      } finally {
        window.removeEventListener('authStateChanged', onAuthChange);
      }
    },
    [],
  );

  return {
    isSupported,
    isRegistering,
    isAuthenticating,
    authenticationStep,
    error,
    register,
    authenticate,
    confirmAuthentication,
    cancelAuthentication,
    listCredentials,
    deactivateCredential,
  };
}

export default useWebAuthn;
