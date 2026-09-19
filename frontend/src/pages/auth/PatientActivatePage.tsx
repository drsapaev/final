/**
 * Patient card activation (Phase 0 PR-A2 frontend, PR-B).
 *
 * Route: /patient/activate (public, landing shell).
 *
 * Flow (registrar-issued activation):
 *   0. Staff issues an activation token (POST /patients/{id}/activation-token)
 *      and hands it to the patient out-of-band (SMS/verbal).
 *   1. activate/request-otp {activation_token} → OTP goes ONLY to the phone
 *      captured on the card at issuance (no phone field by identity contract).
 *   2. activate/confirm {activation_token, code} → atomic User+UserProfile+
 *      Patient.user_id linking → canonical User(role="Patient") JWT.
 *
 * Deep-link: /patient/activate#token=... prefills the token field. The
 * FRAGMENT form is the canonical handout format (Phase 0 follow-up, owner
 * P2): the browser never transmits the fragment to the server, so the
 * 72h activation credential is invisible to Vercel rewrites, access logs
 * and any infrastructure in front of the SPA. The legacy query form
 * (?token=...) keeps working for links already handed out within the TTL.
 * The token is NEVER auto-submitted — the user explicitly continues
 * (stale/revoked tokens surface as a uniform 400 on submit, not on page
 * load). The token is copied into state and immediately stripped from the
 * URL (history replace), so the credential never lingers in the address
 * bar or browser history.
 *
 * Session: same canonical session storage as /patient/login.
 */
import { useCallback, useEffect, useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { KeyRound, ShieldCheck } from 'lucide-react';
import { Alert, Button, Card, CardContent, CardHeader, CardTitle, Input } from '../../components/ui/macos';
import { ensureCSRFToken } from '../../api/client';
import { confirmActivation, requestActivationOtp } from '../../api/patientAccess';
import { replaceAccessOnlySession } from '../../stores/auth';
import { takePatientActivationFragmentToken } from '../../utils/patientActivateDeepLink';
import { getRouteForProfile } from '../../constants/routes';
import { useTranslation } from '../../i18n/useTranslation';
import logger from '../../utils/logger';
import type { HttpApiError } from '../../types/errors';

type PatientActivateStep = 'token' | 'code';

const cardShellStyle: CSSProperties = {
  minHeight: '100vh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '24px',
  background:
    'linear-gradient(160deg, var(--mac-bg-primary, #f5f5f7) 0%, var(--mac-bg-secondary, #e8e8ed) 100%)',
};

const footerLinkStyle: CSSProperties = {
  color: 'var(--mac-accent-blue, #007aff)',
  textDecoration: 'none',
  fontWeight: 500,
};

const PatientActivatePage = () => {
  const { t: rawT, language } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const [step, setStep] = useState<PatientActivateStep>('token');
  const [activationToken, setActivationToken] = useState('');
  const [code, setCode] = useState('');
  const [maskedPhone, setMaskedPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Deep-link prefill (#token=... fragment, legacy ?token=... query) —
  // prefill only, never auto-submit. Phase 0 PR-B review P2 + follow-up
  // (owner P2, Codex P1): after copying the credential into state it is
  // immediately stripped from the URL (address bar, browser history,
  // copy-paste) with replace:true. The fragment is normally extracted and
  // stripped BEFORE telemetry init by main.tsx (utils/patientActivate-
  // DeepLink) — this page then consumes the one-shot stash first; the
  // router-location fragment/query reads below remain as the fallback for
  // environments without the bootstrap extraction (tests). The legacy
  // query form is kept for links already handed out (72h TTL). Unrelated
  // query params are preserved; the re-run of this effect after the strip
  // resolves to an empty prefill, so this cannot loop.
  useEffect(() => {
    const hashParams = new URLSearchParams((location.hash || '').replace(/^#/, ''));
    const fromHash = (hashParams.get('token') || '').trim();
    const fromQuery = (searchParams.get('token') || '').trim();
    const prefill = takePatientActivationFragmentToken() || fromHash || fromQuery;
    if (!prefill) {
      return;
    }
    setActivationToken(prefill);
    const next = new URLSearchParams(searchParams);
    next.delete('token');
    navigate(
      { pathname: location.pathname, search: next.toString(), hash: '' },
      { replace: true }
    );
  }, [location.hash, location.pathname, navigate, searchParams]);

  const normalizeError = useCallback(
    (err: unknown) => {
      const apiError = err as HttpApiError;
      const status = apiError?.response?.status;
      if (status === 429) {
        return t('patientPortal.pa_rate_limited');
      }
      if (status === 503) {
        return t('patientPortal.pa_unavailable');
      }
      if (status === 409) {
        return t('patientPortal.pa_already_linked');
      }
      // Uniform 400 (invalid/stale token, wrong code) — no detail by contract.
      return t('patientPortal.pa_error');
    },
    [t]
  );

  const handleRequestOtp = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const token = activationToken.trim();
    if (token.length < 16 || token.length > 256) {
      // Backend contract (openapi PatientActivationOtpRequest/ConfirmRequest):
      // minLength 16, maxLength 256; the issued token is
      // secrets.token_urlsafe(32) (~43 chars). Only the length sanity check
      // is mirrored client-side — real validity is a uniform 400 server-side.
      setError(t('patientPortal.pa_token_invalid'));
      return;
    }

    setLoading(true);
    try {
      const locale = language === 'uz' || language === 'uz-Latn' || language === 'uz-Cyrl' ? 'uz' : 'ru';
      const response = await requestActivationOtp({ activation_token: token, locale });
      setMaskedPhone(response.phone_masked || '');
      setCode('');
      setStep('code');
    } catch (err) {
      logger.warn('[PatientActivate] request-otp failed:', err);
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const trimmedCode = code.trim();
    if (!/^\d{6}$/.test(trimmedCode)) {
      setError(t('patientPortal.pa_code_invalid'));
      return;
    }

    setLoading(true);
    try {
      const session = await confirmActivation({
        activation_token: activationToken.trim(),
        code: trimmedCode,
      });

      const accessToken = session.access_token.trim();
      // Phase 0 PR-B review P1: access-only session replacement — see
      // PatientLoginPage / stores/auth.replaceAccessOnlySession. A leftover
      // staff refresh_token must never survive into the patient session.
      replaceAccessOnlySession(accessToken, session.user as unknown as Record<string, unknown>);
      ensureCSRFToken().catch(() => {
        // Non-fatal — the request interceptor fetches CSRF on demand.
      });

      const target = getRouteForProfile(session.user as unknown as Record<string, unknown>);
      navigate(target, { replace: true });
    } catch (err) {
      logger.warn('[PatientActivate] confirm failed:', err);
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleBackToToken = () => {
    setStep('token');
    setCode('');
    setMaskedPhone('');
    setError('');
  };

  return (
    <div style={cardShellStyle}>
      <Card variant="default" style={{ width: '100%', maxWidth: 420 }}>
        <CardHeader>
          <CardTitle style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShieldCheck size={20} aria-hidden="true" />
            {t('patientPortal.pa_title')}
          </CardTitle>
          <p style={{ margin: '6px 0 0', color: 'var(--mac-text-secondary, #6e6e73)', fontSize: 14 }}>
            {t('patientPortal.pa_subtitle')}
          </p>
        </CardHeader>
        <CardContent>
          {error ? (
            <Alert variant="danger" style={{ marginBottom: 16 }} role="alert">
              {error}
            </Alert>
          ) : null}

          {step === 'token' ? (
            <form onSubmit={handleRequestOtp} noValidate>
              <label htmlFor="patient-activate-token" style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                {t('patientPortal.pa_token_label')}
              </label>
              <Input
                id="patient-activate-token"
                name="activation_token"
                type="text"
                autoComplete="off"
                spellCheck={false}
                placeholder={t('patientPortal.pa_token_placeholder')}
                value={activationToken}
                onChange={(event) => setActivationToken(event.target.value)}
                disabled={loading}
                required
              />
              <Button type="submit" disabled={loading} style={{ width: '100%', marginTop: 16 }} aria-label={t('patientPortal.pa_continue')}>
                <KeyRound size={16} style={{ marginRight: 8 }} aria-hidden="true" />
                {loading ? t('patientPortal.pa_checking') : t('patientPortal.pa_continue')}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleConfirm} noValidate>
              {maskedPhone ? (
                <p style={{ margin: '0 0 12px', fontSize: 14, color: 'var(--mac-text-secondary, #6e6e73)' }}>
                  {t('patientPortal.pa_otp_sent_to', { phone: maskedPhone })}
                </p>
              ) : null}
              <label htmlFor="patient-activate-code" style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                {t('patientPortal.pa_code_label')}
              </label>
              <Input
                id="patient-activate-code"
                name="code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                placeholder={t('patientPortal.pa_code_placeholder')}
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                disabled={loading}
                autoFocus
                required
              />
              <Button type="submit" disabled={loading} style={{ width: '100%', marginTop: 16 }} aria-label={t('patientPortal.pa_confirm')}>
                <ShieldCheck size={16} style={{ marginRight: 8 }} aria-hidden="true" />
                {loading ? t('patientPortal.pa_confirming') : t('patientPortal.pa_confirm')}
              </Button>
              <div style={{ marginTop: 12, fontSize: 13 }}>
                <button
                  type="button"
                  onClick={handleBackToToken}
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', ...footerLinkStyle }}
                >
                  {t('patientPortal.pa_back_to_token')}
                </button>
              </div>
            </form>
          )}

          <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--mac-border, #d2d2d7)', fontSize: 13, color: 'var(--mac-text-secondary, #6e6e73)' }}>
            {t('patientPortal.pa_have_account_hint')}{' '}
            <Link to="/patient/login" style={footerLinkStyle}>
              {t('patientPortal.pa_have_account_link')}
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PatientActivatePage;
