/**
 * useWebAuthn — P5 frontend integration for passkey registration/login.
 *
 * Uses Web Authentication API (navigator.credentials) to register
 * and authenticate with passkeys. Requires HTTPS (or localhost).
 *
 * Usage:
 *   const { isSupported, register, authenticate, listCredentials } = useWebAuthn();
 *
 *   // Register new passkey:
 *   await register({ name: 'iPhone 15' });
 *
 *   // Authenticate with existing passkey:
 *   const result = await authenticate();
 *   // result = { access_token, refresh_token, ... }
 */
import { useState, useCallback } from 'react';
import { api } from '../../api/client';

function base64urlToBuffer(base64url) {
  const padding = '='.repeat((4 - (base64url.length % 4)) % 4);
  const base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(base64);
  const buffer = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    buffer[i] = binary.charCodeAt(i);
  }
  return buffer.buffer;
}

function bufferToBase64url(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

export function useWebAuthn() {
  const [isRegistering, setIsRegistering] = useState(false);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [error, setError] = useState('');

  const isSupported = typeof window !== 'undefined' &&
    typeof window.PublicKeyCredential !== 'undefined';

  const register = useCallback(async (options = {}) => {
    if (!isSupported) {
      setError('webauthn_not_supported');
      return false;
    }

    setIsRegistering(true);
    setError('');

    try {
      // Get JWT token for auth
      const token = sessionStorage.getItem('patient_jwt_token');
      if (!token) {
        setError('not_authenticated');
        return false;
      }

      // Step 1: Begin registration
      const beginResponse = await api.post('/webauthn/register/begin', {
        credential_name: options.name,
        rp_id: options.rpId || window.location.hostname,
        rp_name: options.rpName || 'Medical Clinic',
      });

      const optionsData = beginResponse.data.options;

      // Step 2: Create credential via browser
      const publicKeyOptions = {
        challenge: base64urlToBuffer(optionsData.challenge),
        rp: {
          id: optionsData.rp.id,
          name: optionsData.rp.name,
        },
        user: {
          id: base64urlToBuffer(optionsData.user.id),
          name: optionsData.user.name,
          displayName: optionsData.user.displayName,
        },
        pubKeyCredParams: optionsData.pubKeyCredParams || [
          { type: 'public-key', alg: -7 },
        ],
        timeout: optionsData.timeout || 60000,
        attestation: 'none',
      };

      const credential = await navigator.credentials.create({
        publicKey: publicKeyOptions,
      });

      if (!credential) {
        setError('registration_cancelled');
        return false;
      }

      // Step 3: Finish registration
      const attestationResponse = credential.response;
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
      setError(err?.response?.data?.detail?.reason || 'registration_failed');
      return false;
    } finally {
      setIsRegistering(false);
    }
  }, [isSupported]);

  const authenticate = useCallback(async (options) => {
    if (!isSupported) {
      setError('webauthn_not_supported');
      return null;
    }

    setIsAuthenticating(true);
    setError('');

    try {
      // Step 1: Begin authentication
      const beginResponse = await api.post('/webauthn/login/begin', {
        patient_id: options.patientId,
        rp_id: options.rpId || window.location.hostname,
      });

      const optionsData = beginResponse.data.options;

      // Step 2: Get credential via browser
      const publicKeyOptions = {
        challenge: base64urlToBuffer(optionsData.challenge),
        rpId: optionsData.rpId,
        timeout: optionsData.timeout || 60000,
        userVerification: 'preferred',
      };

      const assertion = await navigator.credentials.get({
        publicKey: publicKeyOptions,
      });

      if (!assertion) {
        setError('authentication_cancelled');
        return null;
      }

      // Step 3: Finish authentication
      const assertionResponse = assertion.response;
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

      // Store JWT tokens
      const data = finishResponse.data;
      if (data?.access_token) {
        sessionStorage.setItem('patient_jwt_token', data.access_token);
        sessionStorage.setItem('patient_refresh_token', data.refresh_token);
        sessionStorage.setItem(
          'patient_token_expires_at',
          String(Date.now() + (data.expires_in * 1000))
        );
      }

      return data;
    } catch (err) {
      setError(err?.response?.data?.detail?.reason || 'authentication_failed');
      return null;
    } finally {
      setIsAuthenticating(false);
    }
  }, [isSupported]);

  const listCredentials = useCallback(async () => {
    try {
      const response = await api.post('/webauthn/credentials/list', {});
      return response.data?.credentials || [];
    } catch {
      return [];
    }
  }, []);

  const deactivateCredential = useCallback(async (credentialId) => {
    try {
      await api.post(`/webauthn/credentials/${credentialId}/deactivate`, {});
      return true;
    } catch {
      return false;
    }
  }, []);

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
