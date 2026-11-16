
import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, Button, Alert, Input } from '../ui/macos';
import { useWebAuthn } from '../../hooks/useWebAuthn';
import { requestPatientOtp, verifyPatientOtp } from '../../api/patientAccess';
import { isValidUzbekPhone, normalizeUzbekPhoneForApi } from '../../utils/phoneUtils';
import { tokenManager } from '../../utils/tokenManager';
import type { HttpApiError } from '../../types/errors';
import { useTranslation } from '../../i18n/useTranslation';
import React from 'react';
import { Plus, ShieldCheck, Trash2 } from 'lucide-react';
import '../../pages/patient.css';

/**
 * WebAuthn Registration UI — P5 frontend integration.
 *
 * Allows patients to register passkeys (TouchID/FaceID/YubiKey) as
 * an alternative to Telegram Mini App authentication.
 */
interface WebAuthnCredential {
  id: string | number;
  name?: string;
  device_type?: string;
  last_used_at?: string;
}

export default function WebAuthnRegistration({ patientId }: { patientId?: string | number | null }) {
  const { t, language } = useTranslation();
  void patientId;
  const { isSupported, isRegistering, error, register, listCredentials, deactivateCredential } = useWebAuthn();
  const [credentials, setCredentials] = useState<WebAuthnCredential[]>([]);
  const [credentialName, setCredentialName] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const loadVersion = useRef(0);
  const actionVersion = useRef(0);
  const busyRef = useRef(false);
  const [action, setAction] = useState<{ kind: 'register'; name: string } | { kind: 'deactivate'; id: string | number } | null>(null);
  const [step, setStep] = useState<'phone' | 'code'>('phone');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [otpError, setOtpError] = useState('');
  const actionToken = useRef<string | null>(null);

  const loadCredentials = useCallback(async () => {
    const version = ++loadVersion.current;
    setLoading(true);
    setLoadError(false);
    try {
      const creds = await listCredentials();
      if (version === loadVersion.current) setCredentials(creds as WebAuthnCredential[]);
    } catch {
      if (version === loadVersion.current) {
        setCredentials([]);
        setLoadError(true);
      }
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }, [listCredentials]);

  useEffect(() => {
    void loadCredentials();
    const onAuthChange = () => {
      loadVersion.current += 1;
      actionVersion.current += 1;
      actionToken.current = null;
      setCredentials([]);
      setLoading(false);
      setLoadError(true);
      setAction(null);
      setPhone('');
      setCode('');
      setOtpError('');
      setBusy(false);
    };
    window.addEventListener('authStateChanged', onAuthChange);
    return () => {
      window.removeEventListener('authStateChanged', onAuthChange);
      loadVersion.current += 1;
      actionVersion.current += 1;
    };
  }, [loadCredentials]);

  const startAction = (next: NonNullable<typeof action>) => {
    if (busyRef.current || action) return;
    actionVersion.current += 1;
    actionToken.current = tokenManager.getAccessToken();
    setAction(next);
    setStep('phone');
    setPhone('');
    setCode('');
    setOtpError('');
  };

  const cancelAction = () => {
    actionVersion.current += 1;
    actionToken.current = null;
    setAction(null);
    setPhone('');
    setCode('');
    setOtpError('');
  };

  const sessionIsCurrent = () => !!actionToken.current && tokenManager.getAccessToken() === actionToken.current;
  const errorFor = (err: unknown) => {
    const status = (err as HttpApiError)?.response?.status;
    return t(status === 503 ? 'patientPortal.pl_unavailable' : status === 429
      ? 'patientPortal.pl_rate_limited' : 'patient.pat_web_otp_error');
  };

  const requestCode = async () => {
    if (busyRef.current) return;
    if (!sessionIsCurrent()) { setOtpError(t('patient.pat_web_err_not_authenticated')); return; }
    if (!isValidUzbekPhone(phone)) { setOtpError(t('patientPortal.pl_phone_invalid')); return; }
    const version = actionVersion.current;
    const normalized = normalizeUzbekPhoneForApi(phone);
    busyRef.current = true; setBusy(true); setOtpError('');
    try {
      await requestPatientOtp({ phone: normalized, locale: language === 'uz' || language === 'uz-Latn' || language === 'uz-Cyrl' ? 'uz' : 'ru' });
      if (version !== actionVersion.current) return;
      if (!sessionIsCurrent()) { setOtpError(t('patient.pat_web_err_not_authenticated')); return; }
      setPhone(normalized); setStep('code');
    } catch (err) {
      if (version === actionVersion.current) setOtpError(errorFor(err));
    } finally {
      busyRef.current = false;
      if (version === actionVersion.current) setBusy(false);
    }
  };

  const confirmAction = async () => {
    if (busyRef.current || !action) return;
    if (!sessionIsCurrent()) { setOtpError(t('patient.pat_web_err_not_authenticated')); return; }
    if (!/^\d{6}$/.test(code.trim())) { setOtpError(t('patientPortal.pl_code_invalid')); return; }
    const version = actionVersion.current;
    busyRef.current = true; setBusy(true); setOtpError('');
    let grantIssued = false;
    try {
      const result = await verifyPatientOtp({ phone, code: code.trim() });
      grantIssued = true;
      if (version !== actionVersion.current) return;
      if (!sessionIsCurrent()) { setOtpError(t('patient.pat_web_err_not_authenticated')); return; }
      const stepUp = { phone, verification_grant: result.verification_grant };
      const success = action.kind === 'register'
        ? await register({ ...stepUp, name: action.name })
        : await deactivateCredential(action.id, stepUp);
      if (version !== actionVersion.current) return;
      const sameSession = sessionIsCurrent();
      setBusy(false);
      cancelAction();
      if (success && sameSession) { setCredentialName(''); await loadCredentials(); }
    } catch (err) {
      if (version === actionVersion.current) {
        if (grantIssued) { setBusy(false); cancelAction(); }
        setOtpError(errorFor(err));
      }
    } finally {
      busyRef.current = false;
      if (version === actionVersion.current) setBusy(false);
    }
  };

  if (!isSupported) {
    return (
      <Card variant="filled" padding="default">
        <CardContent>
          <Alert severity="warning">
            {t('patient.pat_web_not_supported')}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="filled" padding="none">
      <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '12px 16px' }}>
        <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <ShieldCheck size={20} aria-hidden="true" />
          {t('patient.pat_web_title')}
        </CardTitle>
      </CardHeader>
      <CardContent style={{ padding: '16px', display: 'grid', gap: '16px' }}>
        {/* Registration form */}
        {!loading && !loadError && <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
          <label style={{ flex: 1 }}>
            {t('patient.pat_web_device_name')}
            <Input
              maxLength={100}
              value={credentialName}
              onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setCredentialName(e.target.value)}
              placeholder={t('patient.pat_web_device_name_placeholder')}
              disabled={isRegistering || !!action || busy}
            />
          </label>
          <Button
            variant="primary"
            onClick={() => startAction({ kind: 'register', name: credentialName.trim() || t('patient.pat_web_passkey_default', { date: new Date().toLocaleDateString() }) })}
            loading={isRegistering}
            disabled={isRegistering || !!action}
          >
            <Plus size={16} aria-hidden="true" />
            {isRegistering ? t('patient.pat_web_registering') : t('patient.pat_web_add_passkey')}
          </Button>
        </div>}

        {action && (
          <div className="passkey-step-up">
            <p>{t(action.kind === 'register' ? 'patient.pat_web_verify_add' : 'patient.pat_web_verify_delete')}</p>
            {step === 'phone' ? (
              <label>{t('patientPortal.pl_phone_label')}<Input value={phone} disabled={busy} onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setPhone(e.target.value)} placeholder={t('patientPortal.pl_phone_placeholder')} type="tel" autoComplete="tel" /></label>
            ) : (
              <label>{t('patientPortal.pl_code_label')}<Input value={code} disabled={busy} onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setCode(e.target.value)} placeholder={t('patientPortal.pl_code_placeholder')} autoComplete="one-time-code" inputMode="numeric" /></label>
            )}
            {otpError && <Alert severity="error">{otpError}</Alert>}
            <div className="passkey-step-up-actions">
              <Button variant="primary" disabled={busy} loading={busy} onClick={step === 'phone' ? requestCode : confirmAction}>
                {t(step === 'phone' ? 'patientPortal.pl_send_code' : 'patient.pat_web_confirm')}
              </Button>
              <Button variant="outline" disabled={busy} onClick={cancelAction}>{t('patient.pat_web_cancel')}</Button>
            </div>
          </div>
        )}
        {!action && otpError && <Alert severity="error">{otpError}</Alert>}

        {error && (
          <Alert severity="error">
            {error === 'webauthn_not_supported' && t('patient.pat_web_err_not_supported')}
            {error === 'not_authenticated' && t('patient.pat_web_err_not_authenticated')}
            {error === 'registration_cancelled' && t('patient.pat_web_err_cancelled')}
            {error === 'registration_failed' && t('patient.pat_web_err_failed')}
            {error === 'management_unavailable' && t('patient.pat_web_unavailable')}
            {error === 'step_up_failed' && t('patient.pat_web_otp_error')}
            {error === 'deactivation_failed' && t('patient.pat_web_delete_error')}
            {error === 'last_active_credential' && t('patient.pat_web_last_key')}
          </Alert>
        )}

        {/* Credentials list */}
        {loading ? (
          <Alert severity="info">{t('patient.pat_web_loading')}</Alert>
        ) : loadError ? (
          <Alert severity="error">
            {t('patient.pat_web_unavailable')}
            <Button variant="outline" size="small" onClick={loadCredentials}>
              {t('common.refresh')}
            </Button>
          </Alert>
        ) : credentials.length === 0 ? (
          <Alert severity="info">
            {t('patient.pat_web_empty')}
          </Alert>
        ) : (
          <div style={{ display: 'grid', gap: '8px' }}>
            {credentials.map((cred) => (
              <div
                key={cred.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '12px 14px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  background: 'var(--mac-bg-primary)',
                }}
              >
                <div>
                  <div style={{ fontWeight: 500, color: 'var(--mac-text-primary)' }}>
                    {cred.name || t('patient.pat_web_no_name')}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--mac-text-tertiary)' }}>
                    {cred.device_type || t('patient.pat_web_device_default')}
                    {cred.last_used_at ? ` · ${t('patient.pat_web_last_used', { date: new Date(cred.last_used_at).toLocaleDateString('ru-RU') })}` : ''}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="small"
                  disabled={!!action || busy}
                  onClick={() => startAction({ kind: 'deactivate', id: cred.id })}
                >
                  <Trash2 size={14} aria-hidden="true" />
                  {t('patient.pat_web_delete')}
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* Info */}
        <Alert severity="info">
          {t('patient.pat_web_info')}
        </Alert>
      </CardContent>
    </Card>
  );
}

