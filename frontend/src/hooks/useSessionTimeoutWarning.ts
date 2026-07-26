/**
 * useSessionTimeoutWarning — P-021 (UX audit).
 *
 * Surfaces a warning dialog to the doctor 5 minutes before their JWT
 * access token expires, so they can save their work and refresh the
 * session instead of losing data to a silent 401 on the next save.
 *
 * The token refresh logic already lives in api/client.js
 * (isTokenExpiringSoon + refreshTokenIfNeeded) — this hook only adds
 * the user-facing warning UI. It polls the token's `exp` claim every
 * 30 seconds; when the remaining time drops below the warning threshold,
 * it calls `(onWarning as (...args: unknown[]) => void)(expiresAt)` so the parent can show a dialog.
 * When the token actually expires, it calls `(onExpired as (...args: unknown[]) => void)()`.
 *
 * Usage:
 *   useSessionTimeoutWarning({
 *     onWarning: (expiresAt) => setShowWarningDialog(true),
 *     onExpired: () => navigate('/login'),
 *     warningThresholdMs: 5 * 60 * 1000, // 5 minutes
 *     pollIntervalMs: 30 * 1000,         // 30 seconds
 *   });
 */

import { useEffect, useRef } from 'react';
import logger from '../utils/logger';

const DEFAULT_WARNING_THRESHOLD = 5 * 60 * 1000; // 5 minutes
const DEFAULT_POLL_INTERVAL = 30 * 1000; // 30 seconds

/**
 * Parse the `exp` claim from a JWT without verifying the signature.
 * Returns the expiration time in milliseconds (epoch), or null if the
 * token is not a JWT or has no exp claim.
 */
function getTokenExpiryMs(token: string) {
  if (!token) return null;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    if (!payload.exp) return null;
    return payload.exp * 1000;
  } catch {
    return null;
  }
}

export interface UseSessionTimeoutWarningOptions {
  onWarning?: (expiresAt: Date) => void;
  onExpired?: () => void;
  warningThresholdMs?: number;
  pollIntervalMs?: number;
  enabled?: boolean;
}

export function useSessionTimeoutWarning({
  onWarning,
  onExpired,
  warningThresholdMs = DEFAULT_WARNING_THRESHOLD,
  pollIntervalMs = DEFAULT_POLL_INTERVAL,
  enabled = true,
}: UseSessionTimeoutWarningOptions = {}) {
  const warningFiredRef = useRef(false);
  const expiredFiredRef = useRef(false);

  // audit/phase-4, BS-21: keep latest callbacks in refs so the polling
  // interval always invokes the CURRENT closure. Previously `check` captured
  // the FIRST-render `onWarning`/`onExpired` (deps array excluded them on
  // purpose to avoid re-subscribing), so a parent that re-created these
  // closures (extremely common — `onWarning={() => setShowWarningDialog(true)}`
  // capturing state) was stuck with stale callbacks forever. If those
  // closures depended on state that changed between renders, the dialog
  // would either not show or show with stale data.
  // The ref-update effect runs on every render (no dep array) — cheap, and
  // guarantees the polling `check` sees the latest. This is the same
  // pattern useAdminData uses for onErrorRef/onSuccessRef.
  const onWarningRef = useRef(onWarning);
  const onExpiredRef = useRef(onExpired);
  onWarningRef.current = onWarning;
  onExpiredRef.current = onExpired;

  useEffect(() => {
    if (!enabled) return;
    if (typeof onWarning !== 'function' && typeof onExpired !== 'function') {
      // Nothing to do — bail out early.
      return;
    }

    let intervalId = null;

    const check = () => {
      try {
        // PR-39 / P0-2: read token from sessionStorage (tokenManager migration)
        const token = window.sessionStorage.getItem('auth_token');
        if (!token) {
          // No token at all — the auth guard will handle redirect.
          return;
        }

        const expiresAt = getTokenExpiryMs(token);
        if (!expiresAt) {
          // Not a JWT or no exp claim — can't warn, leave it to the API layer.
          return;
        }

        const remaining = expiresAt - Date.now();

        if (remaining <= 0) {
          if (!expiredFiredRef.current) {
            expiredFiredRef.current = true;
            warningFiredRef.current = true; // no point warning after expiry
            logger.info('[useSessionTimeoutWarning] session expired');
            // Call through the ref so we get the latest closure.
            const fn = onExpiredRef.current;
            if (typeof fn === 'function') fn();
          }
          return;
        }

        if (remaining <= warningThresholdMs) {
          if (!warningFiredRef.current) {
            warningFiredRef.current = true;
            logger.info(
              `[useSessionTimeoutWarning] session expiring in ${Math.round(remaining / 1000)}s`
            );
            // Call through the ref so we get the latest closure.
            const fn = onWarningRef.current;
            if (typeof fn === 'function') fn(new Date(expiresAt));
          }
        } else {
          // Token was refreshed (or user logged in anew) — reset the flags
          // so the warning can fire again on the next cycle.
          if (warningFiredRef.current) {
            warningFiredRef.current = false;
            expiredFiredRef.current = false;
          }
        }
      } catch (err) {
        logger.warn('[useSessionTimeoutWarning] check failed', err);
      }
    };

    // Run immediately, then on interval.
    check();
    intervalId = setInterval(check, pollIntervalMs);

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
    // onWarning/onExpired are intentionally NOT in deps — the refs above
    // keep the latest closures without forcing re-subscription. The
    // interval is re-created only when timing/config deps change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, warningThresholdMs, pollIntervalMs]);
}

export default useSessionTimeoutWarning;
