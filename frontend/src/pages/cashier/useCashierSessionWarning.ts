/**
 * PR-UI-14-3: cashier session-timeout warning slice.
 *
 * Verbatim move of the sessionWarning/sessionSecondsLeft useState pair +
 * useSessionTimeoutWarning wiring + 1-second countdown effect from
 * CashierPanel (Deferred #1 + UX Audit #2.5). No behavior changes.
 *
 * The hook owns:
 *  - warning state { active, expiresAt } and the seconds-left countdown
 *  - the onWarning/onExpired callbacks (notify + /login redirect verbatim)
 *
 * The panel keeps only the render side (warning dialog JSX) and
 * dismissSessionWarning() for the two dialog buttons.
 */

import { useEffect, useState } from 'react';

import notify from '../../services/notify';
import { useTranslation } from '../../i18n/useTranslation';
import { useSessionTimeoutWarning } from '../../hooks/useSessionTimeoutWarning';

export interface CashierSessionWarning {
  active: boolean;
  expiresAt?: number;
}

export const useCashierSessionWarning = () => {
  const { t: tI18n } = useTranslation();
  // Deferred #1: session timeout warning — prevents silent JWT expiry while
  // cashier is processing a payment. Mirrors all other clinical panels.
  const [sessionWarning, setSessionWarning] = useState<CashierSessionWarning | null>(null);
  // UX Audit #2.5: счётчик секунд до истечения сессии.
  const [sessionSecondsLeft, setSessionSecondsLeft] = useState<number | null>(null);
  useSessionTimeoutWarning({
    onWarning: (expiresAt) => {
      // UX Audit #2.5: сохраняем expiresAt для счётчика обратного отсчёта.
      const ms = expiresAt ? (Number(expiresAt) - Date.now()) : 60 * 1000;
      setSessionWarning({ active: true, expiresAt: expiresAt ? Number(expiresAt) : undefined });
      setSessionSecondsLeft(Math.max(0, Math.floor(ms / 1000)));
    },
    onExpired: () => {
      setSessionWarning(null);
      setSessionSecondsLeft(null);
      notify.error(tI18n('cashier.session_expired'));
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  // UX Audit #2.5: тикаем каждую секунду, пока показано предупреждение.
  useEffect(() => {
    if (!sessionWarning?.active || !sessionWarning.expiresAt) return undefined;
    const tick = () => {
      const ms = (sessionWarning.expiresAt ?? 0) - Date.now();
      setSessionSecondsLeft(Math.max(0, Math.floor(ms / 1000)));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [sessionWarning]);

  const dismissSessionWarning = () => {
    setSessionWarning(null);
  };

  return {
    sessionWarning,
    sessionSecondsLeft,
    dismissSessionWarning,
  };
};
