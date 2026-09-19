/**
 * Patient portal login (Phase 0 PR-A1 frontend, PR-B).
 *
 * Route: /patient/login (public, landing shell).
 *
 * Flow (phone OTP, fail-closed backend):
 *   1. request-otp  {phone}                → uniform response (anti-enum)
 *   2. verify-otp   {phone, code}          → one-time verification_grant
 *   3. login        {phone, grant}         → canonical User(role="Patient") JWT
 *
 * Session: the returned JWT is stored via the standard auth store
 * (setToken/setProfile) — NOT the legacy webauthn patient keys — so the
 * existing RouteAccessBoundary grants access to the role-scoped /patient
 * home (homeForRoles: ['patient']).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LogIn, Phone, ShieldCheck } from 'lucide-react';
import { Alert, Button, Card, CardContent, CardHeader, CardTitle, Input } from '../../components/ui/macos';
import { ensureCSRFToken } from '../../api/client';
import { patientLogin, requestPatientOtp, verifyPatientOtp } from '../../api/patientAccess';
import { replaceAccessOnlySession } from '../../stores/auth';
import { getRouteForProfile } from '../../constants/routes';
import { isValidUzbekPhone, normalizeUzbekPhoneForApi } from '../../utils/phoneUtils';
import { useTranslation } from '../../i18n/useTranslation';
import logger from '../../utils/logger';
import type { HttpApiError } from '../../types/errors';

type PatientLoginStep = 'phone' | 'code';

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

const PatientLoginPage = () => {
  const { t: rawT, language } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const navigate = useNavigate();

  const [step, setStep] = useState<PatientLoginStep>('phone');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resendAfter, setResendAfter] = useState(0);
  const resendTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (resendTimerRef.current !== null) {
        window.clearInterval(resendTimerRef.current);
      }
    };
  }, []);

  const startResendCountdown = useCallback((seconds: number) => {
    if (resendTimerRef.current !== null) {
      window.clearInterval(resendTimerRef.current);
    }
    setResendAfter(seconds);
    resendTimerRef.current = window.setInterval(() => {
      setResendAfter((prev) => {
        if (prev <= 1) {
          if (resendTimerRef.current !== null) {
            window.clearInterval(resendTimerRef.current);
            resendTimerRef.current = null;
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  const normalizeError = useCallback(
    (err: unknown, fallbackKey: string) => {
      const apiError = err as HttpApiError;
      const status = apiError?.response?.status;
      // Uniform anti-enum bodies carry no usable detail for end users; map by status.
      if (status === 429) {
        return t('patientPortal.pl_rate_limited');
      }
      if (status === 503) {
        return t('patientPortal.pl_unavailable');
      }
      return t(fallbackKey);
    },
    [t]
  );

  const handleRequestOtp = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const normalized = normalizeUzbekPhoneForApi(phone);
    if (!isValidUzbekPhone(phone)) {
      setError(t('patientPortal.pl_phone_invalid'));
      return;
    }

    setLoading(true);
    try {
      const locale = language === 'uz' || language === 'uz-Latn' || language === 'uz-Cyrl' ? 'uz' : 'ru';
      const response = await requestPatientOtp({ phone: normalized, locale });
      startResendCountdown(response.resend_after_seconds || 60);
      setPhone(normalized);
      setStep('code');
    } catch (err) {
      logger.warn('[PatientLogin] request-otp failed:', err);
      setError(normalizeError(err, 'patientPortal.pl_login_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyAndLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const trimmedCode = code.trim();
    if (!/^\d{6}$/.test(trimmedCode)) {
      setError(t('patientPortal.pl_code_invalid'));
      return;
    }

    setLoading(true);
    try {
      // Step 2+3: verify OTP → one-time grant → canonical patient session.
      const grantResponse = await verifyPatientOtp({ phone, code: trimmedCode });
      const session = await patientLogin({ phone, verification_grant: grantResponse.verification_grant });

      const accessToken = session.access_token.trim();
      // Phase 0 PR-B review P1: patient sessions are access-only (no refresh
      // token). REPLACE any previous staff principal in this tab — never merge
      // with it. A leftover staff refresh_token would be replayed on
      // /authentication/refresh once the patient JWT nears expiry, silently
      // minting a fresh staff access token (hidden principal swap).
      replaceAccessOnlySession(accessToken, session.user as unknown as Record<string, unknown>);
      ensureCSRFToken().catch(() => {
        // Non-fatal — the request interceptor fetches CSRF on demand.
      });

      const target = getRouteForProfile(session.user as unknown as Record<string, unknown>);
      navigate(target, { replace: true });
    } catch (err) {
      logger.warn('[PatientLogin] verify/login failed:', err);
      setError(normalizeError(err, 'patientPortal.pl_login_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendAfter > 0 || loading) {
      return;
    }
    setError('');
    setLoading(true);
    try {
      const locale = language === 'uz' || language === 'uz-Latn' || language === 'uz-Cyrl' ? 'uz' : 'ru';
      const response = await requestPatientOtp({ phone, locale });
      startResendCountdown(response.resend_after_seconds || 60);
    } catch (err) {
      logger.warn('[PatientLogin] resend failed:', err);
      setError(normalizeError(err, 'patientPortal.pl_login_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleBackToPhone = () => {
    setStep('phone');
    setCode('');
    setError('');
    if (resendTimerRef.current !== null) {
      window.clearInterval(resendTimerRef.current);
      resendTimerRef.current = null;
    }
    setResendAfter(0);
  };

  return (
    <div style={cardShellStyle}>
      <Card variant="default" style={{ width: '100%', maxWidth: 420 }}>
        <CardHeader>
          <CardTitle style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShieldCheck size={20} aria-hidden="true" />
            {t('patientPortal.pl_title')}
          </CardTitle>
          <p style={{ margin: '6px 0 0', color: 'var(--mac-text-secondary, #6e6e73)', fontSize: 14 }}>
            {t('patientPortal.pl_subtitle')}
          </p>
        </CardHeader>
        <CardContent>
          {error ? (
            <Alert variant="danger" style={{ marginBottom: 16 }} role="alert">
              {error}
            </Alert>
          ) : null}

          {step === 'phone' ? (
            <form onSubmit={handleRequestOtp} noValidate>
              <label htmlFor="patient-login-phone" style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                {t('patientPortal.pl_phone_label')}
              </label>
              <Input
                id="patient-login-phone"
                name="phone"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                placeholder={t('patientPortal.pl_phone_placeholder')}
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                disabled={loading}
                required
              />
              <Button type="submit" disabled={loading} style={{ width: '100%', marginTop: 16 }} aria-label={t('patientPortal.pl_send_code')}>
                <LogIn size={16} style={{ marginRight: 8 }} aria-hidden="true" />
                {loading ? t('patientPortal.pl_sending') : t('patientPortal.pl_send_code')}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleVerifyAndLogin} noValidate>
              <p style={{ margin: '0 0 12px', fontSize: 14, color: 'var(--mac-text-secondary, #6e6e73)' }}>
                {t('patientPortal.pl_code_sent_to', { phone })}
              </p>
              <label htmlFor="patient-login-code" style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                {t('patientPortal.pl_code_label')}
              </label>
              <Input
                id="patient-login-code"
                name="code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                placeholder={t('patientPortal.pl_code_placeholder')}
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                disabled={loading}
                autoFocus
                required
              />
              <Button type="submit" disabled={loading} style={{ width: '100%', marginTop: 16 }} aria-label={t('patientPortal.pl_verify')}>
                <Phone size={16} style={{ marginRight: 8 }} aria-hidden="true" />
                {loading ? t('patientPortal.pl_verifying') : t('patientPortal.pl_verify')}
              </Button>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, fontSize: 13 }}>
                <button
                  type="button"
                  onClick={handleBackToPhone}
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', ...footerLinkStyle }}
                >
                  {t('patientPortal.pl_back_to_phone')}
                </button>
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={resendAfter > 0 || loading}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    cursor: resendAfter > 0 ? 'default' : 'pointer',
                    color: 'var(--mac-text-tertiary, #86868b)',
                    ...footerLinkStyle,
                  }}
                >
                  {resendAfter > 0
                    ? t('patientPortal.pl_resend_in', { seconds: resendAfter })
                    : t('patientPortal.pl_resend')}
                </button>
              </div>
            </form>
          )}

          <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--mac-border, #d2d2d7)', fontSize: 13, color: 'var(--mac-text-secondary, #6e6e73)' }}>
            {t('patientPortal.pl_activate_hint')}{' '}
            <Link to="/patient/activate" style={footerLinkStyle}>
              {t('patientPortal.pl_activate_link')}
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PatientLoginPage;
