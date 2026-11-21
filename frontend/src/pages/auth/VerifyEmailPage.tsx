import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Alert, Card, CardContent, CardHeader, CardTitle } from '../../components/ui/macos';
import { api } from '../../api/client';
import { useTranslation } from '../../i18n/useTranslation';
import { extractEmailVerificationCredential, takeEmailVerificationCredential } from '../../utils/emailVerificationDeepLink';
import type { HttpApiError } from '../../types/errors';

type Result = 'success' | 'expired' | 'error';
let verification: Promise<Result> | null = null;
let activeViews = 0;
let resetTimer: ReturnType<typeof setTimeout> | null = null;

function verifyOnce(): Promise<Result> {
  // Handles in-app navigation as well as bootstrap extraction. The address is
  // cleaned before the request starts and the slot is consumed immediately.
  if (extractEmailVerificationCredential()) verification = null;
  const token = takeEmailVerificationCredential();
  if (token) {
    verification = api.post('/authentication/email-verification/confirm', { token }).then(
      (response) => response.data?.success === true ? 'success' : 'error',
      (error: HttpApiError) => error.response?.status === 400 || error.response?.status === 422 ? 'expired' : 'error',
    );
  }
  return verification ?? Promise.resolve('expired');
}

export default function VerifyEmailPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const [status, setStatus] = useState<'loading' | Result>('loading');

  useEffect(() => {
    activeViews += 1;
    if (resetTimer !== null) clearTimeout(resetTimer);
    resetTimer = null;
    let active = true;
    let attempt = 0;
    const run = (fresh: boolean) => {
      if (fresh) verification = null;
      const currentAttempt = ++attempt;
      setStatus('loading');
      void verifyOnce().then((result) => { if (active && currentAttempt === attempt) setStatus(result); });
    };
    const onLinkChanged = () => run(true);
    window.addEventListener('emailVerificationLinkChanged', onLinkChanged);
    run(false);
    return () => {
      active = false;
      window.removeEventListener('emailVerificationLinkChanged', onLinkChanged);
      activeViews -= 1;
      if (activeViews === 0) {
        // StrictMode re-runs effects immediately. Keep the same in-flight
        // operation for that remount, then discard it after a real departure.
        resetTimer = setTimeout(() => { if (activeViews === 0) verification = null; }, 0);
      }
    };
  }, [location.key, location.hash]);

  return (
    <main className="theme-page-shell">
      <Card variant="default">
        <CardHeader><CardTitle>{t('misc.ev_title')}</CardTitle></CardHeader>
        <CardContent>
          {status === 'loading' ? <p role="status">{t('misc.ev_loading')}</p> : (
            <Alert severity={status === 'success' ? 'success' : 'error'} role={status === 'success' ? 'status' : 'alert'}>
              {t(status === 'success' ? 'misc.ev_success' : status === 'expired' ? 'misc.ev_expired' : 'misc.ev_error')}
            </Alert>
          )}
          {status !== 'loading' && <p><Link to="/login">{t('misc.ev_login')}</Link></p>}
        </CardContent>
      </Card>
    </main>
  );
}
