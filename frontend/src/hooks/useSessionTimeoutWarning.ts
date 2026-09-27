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
import { safeJsonParse } from '../utils/safeJsonParse';

const DEFAULT_WARNING_THRESHOLD = 5 * 60 * 1000; // 5 minutes
const DEFAULT_POLL_INTERVAL = 30 * 1000; // 30 seconds

/**
 * Parse the `exp` claim from a JWT without verifying the signature.
 * Returns the expiration time in milliseconds (epoch), or null if the
 * token is not a JWT or has no exp claim.
 *
 * PR 3351 (review round 7, P2): экспортируется для usePendingAwareSessionExpiry —
 * перед отложенным (за pending-операциями) redirect нужно повторно
 * проверить актуальный токен: single-flight refresh в API-клиенте мог
 * уже обновить его, и принудительный logout прерывал бы восстановленную
 * сессию.
 */
export function getTokenExpiryMs(token: string) {
  if (!token) return null;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = safeJsonParse(atob(parts[1]));
    if (!payload.exp) return null;
    return payload.exp * 1000;
  } catch {
    return null;
  }
}

export interface UseSessionTimeoutWarningOptions {
  onWarning?: (expiresAt: Date) => void;
  onExpired?: () => void;
  /**
   * PR 3351 (review round 8, P2): смена ПОКОЛЕНИЯ токена — в sessionStorage
   * появился ДРУГОЙ непустой access token (single-flight refresh в API-клиенте
   * заменил истёкший JWT новым). Сбрасывает warningFired/expiredFired (новый
   * токен — новый жизненный цикл предупреждения) и оповещает владельца
   * (usePendingAwareSessionExpiry → onSessionRecovered: висящее предупреждение
   * «Сессия скоро истечёт» обязано уйти — оно лгало бы уже восстановленной
   * сессии). Снятие токена (logout) коллбек не вызывает — восстановления нет.
   */
  onTokenChanged?: () => void;
  warningThresholdMs?: number;
  pollIntervalMs?: number;
  enabled?: boolean;
}

export function useSessionTimeoutWarning({
  onWarning,
  onExpired,
  onTokenChanged,
  warningThresholdMs = DEFAULT_WARNING_THRESHOLD,
  pollIntervalMs = DEFAULT_POLL_INTERVAL,
  enabled = true,
}: UseSessionTimeoutWarningOptions = {}) {
  const warningFiredRef = useRef(false);
  const expiredFiredRef = useRef(false);
  // PR 3351 (review round 8, P2): последнее увиденное ПОКОЛЕНИЕ токена
  // (сырое значение). Смена значения = refresh: у нового токена — свой
  // жизненный цикл, fired-флаги сбрасываются независимо от его exp.
  const lastTokenRef = useRef<string | null>(null);

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
  const onTokenChangedRef = useRef(onTokenChanged);
  onTokenChangedRef.current = onTokenChanged;

  useEffect(() => {
    if (!enabled) return;
    if (typeof onWarning !== 'function' && typeof onExpired !== 'function') {
      // Nothing to do — bail out early.
      return;
    }

    let intervalId: ReturnType<typeof setInterval> | null = null;

    const check = () => {
      try {
        // PR-39 / P0-2: read token from sessionStorage (tokenManager migration)
        const token = window.sessionStorage.getItem('auth_token');
        // PR 3351 (review round 8, P2): отслеживаем ПОКОЛЕНИЕ токена по его
        // ЗНАЧЕНИЮ, а не только по exp. Прежний сброс fired-флагов жил в
        // else-ветке (remaining > threshold) и пропускал короткоживущие
        // обновления: gen N истёк (expiredFired=true) → refresh → gen N+1 с
        // remaining ≤ threshold → warningFired остаётся true → предупреждение
        // для N+1 НЕ срабатывает, а его истечение НЕ вызывает onExpired —
        // сессия умирает молча, без предупреждения и без redirect. Любая
        // смена значения сбрасывает оба флага; живая смена (обе непустые,
        // разные) дополнительно оповещает onTokenChanged — восстановление
        // сессии ещё до истечения порога.
        if (lastTokenRef.current !== token) {
          const previousToken = lastTokenRef.current;
          lastTokenRef.current = token;
          warningFiredRef.current = false;
          expiredFiredRef.current = false;
          if (previousToken && token) {
            const fn = onTokenChangedRef.current;
            if (typeof fn === 'function') fn();
          }
        }
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
        // PR 3351 (review round 8, P2): поколение уже отслеживается выше по
        // значению токена — else-ветка сброса остаётся как дешёвая подстраховка
        // (экспирация без смены значения здесь недостижима).
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
