import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, CSSProperties, ReactNode } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  Copy,
  Download,
  Eye,
  EyeOff,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';

import { useTranslation } from '../../i18n/useTranslation';
import { api } from '../../api/client';
import { Button, Input } from '../ui/macos';

/**
 * Мастер настройки двухфакторной аутентификации (TOTP).
 *
 * Два контекста, один компонент:
 *  — enrollment при входе (передан enrollmentToken из login-ответа критичной
 *    роли): успешная верификация возвращает нормальные токены, колбэк
 *    onEnrolled завершает вход;
 *  — настройки безопасности профиля (Bearer JWT): завершение через onComplete.
 *
 * Контракт бэкенда: POST /2fa/setup -> { qr_code_url (otpauth://), secret_key,
 * backup_codes }; POST /2fa/verify-setup { totp_code, enrollment_token? } ->
 * { success, access_token?, refresh_token? }.
 *
 * Слой UI: канонические компоненты ui/macos + токены --mac-*; Tailwind —
 * только раскладка, без хардкода цветов.
 */
type TwoFactorSetupWizardProps = {
  onComplete?: () => void;
  onCancel?: () => void;
  enrollmentToken?: string;
  onEnrolled?: (payload: Record<string, unknown>) => void;
};

type AxiosLike = import('axios').AxiosResponse<Record<string, unknown>>;

const TwoFactorSetupWizard = ({
  onComplete,
  onCancel,
  enrollmentToken,
  onEnrolled,
}: TwoFactorSetupWizardProps) => {
  const { t } = useTranslation();
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [recoveryEmail, setRecoveryEmail] = useState('');
  const [setupData, setSetupData] = useState<Record<string, unknown> | null>(null);
  const [code, setCode] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [enrolledPayload, setEnrolledPayload] = useState<Record<string, unknown> | null>(null);
  const [copied, setCopied] = useState('');
  const codeRef = useRef<HTMLInputElement>(null);

  const isEnrollment = Boolean(enrollmentToken);
  const secretKey = String(setupData?.secret_key ?? '');
  const qrValue = String(setupData?.qr_code_url ?? '');

  useEffect(() => {
    if (step === 3) codeRef.current?.focus();
  }, [step]);

  const handleSetup = async () => {
    setLoading(true);
    setError('');
    try {
      const response = (await api.post('/2fa/setup', {
        recovery_email: recoveryEmail || null,
        ...(enrollmentToken ? { enrollment_token: enrollmentToken } : {}),
      })) as unknown as AxiosLike;
      const data = response.data;
      if (response.status >= 200 && response.status < 300 && data.secret_key) {
        setSetupData(data);
        setBackupCodes((data.backup_codes as string[]) || []);
        setStep(2);
      } else {
        setError(String(data.detail || data.message || t('misc.tfsw_setup_error')));
      }
    } catch {
      setError(t('misc.tfsw_setup_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (code.length !== 6) return;
    setLoading(true);
    setError('');
    try {
      const response = (await api.post('/2fa/verify-setup', {
        totp_code: code,
        ...(enrollmentToken ? { enrollment_token: enrollmentToken } : {}),
      })) as unknown as AxiosLike;
      const data = response.data;
      if (response.status >= 200 && response.status < 300 && data.success) {
        if (data.access_token && onEnrolled) {
          // Резервные коды показываем ДО завершения входа: второй шанс их
          // увидеть есть только в настройках профиля (regenerate).
          setEnrolledPayload(data);
          setStep(4);
          return;
        }
        setStep(4);
      } else {
        setError(String(data.detail || data.message || t('misc.tfsw_invalid_code')));
      }
    } catch {
      setError(t('misc.tfsw_code_verify_error'));
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string, marker: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(marker);
      setTimeout(() => setCopied(''), 2000);
    } catch {
      // буфер обмена недоступен — не блокируем флоу
    }
  };

  const downloadBackupCodes = () => {
    const blob = new Blob([backupCodes.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'backup-codes.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const stepTitles = [t('misc.tfsw2_step1_title'), t('misc.tfsw2_step2_title'), t('misc.tfsw2_step3_title')];

  const renderStepper = () => (
    <div
      className="flex items-start justify-center"
      style={{ marginBottom: 'var(--mac-spacing-5)', gap: 'var(--mac-spacing-2)' }}
    >
      {stepTitles.map((title, idx) => {
        const n = idx + 1;
        const done = step > n || step === 4;
        const active = step === n && step !== 4;
        return (
          <div key={title} className="flex flex-col items-center" style={{ width: 96 }}>
            <div className="flex items-center" style={{ gap: 6 }}>
              <div
                aria-label={title}
                className="flex items-center justify-center"
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 'var(--mac-radius-full)',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)' as CSSProperties['fontWeight'],
                  color: done || active ? 'var(--mac-text-inverse)' : 'var(--mac-text-secondary)',
                  background: done || active ? 'var(--mac-accent-blue)' : 'var(--mac-background-tertiary)',
                  transition: 'background 150ms ease',
                }}
              >
                {done ? <CheckCircle style={{ width: 16, height: 16 }} /> : n}
              </div>
              {idx < stepTitles.length - 1 && (
                <div
                  style={{
                    width: 24,
                    height: 2,
                    borderRadius: 1,
                    marginTop: 13,
                    background: step > n ? 'var(--mac-accent-blue)' : 'var(--mac-border-secondary)',
                  }}
                />
              )}
            </div>
            <div
              style={{
                marginTop: 'var(--mac-spacing-1)',
                fontSize: 'var(--mac-font-size-xs)',
                color: active ? 'var(--mac-text-primary)' : 'var(--mac-text-secondary)',
                fontWeight: active ? ('var(--mac-font-weight-medium)' as CSSProperties['fontWeight']) : undefined,
                textAlign: 'center',
                lineHeight: 1.2,
              }}
            >
              {title}
            </div>
          </div>
        );
      })}
    </div>
  );

  const renderError = () =>
    error ? (
      <div
        role="alert"
        aria-live="polite"
        className="flex items-start gap-2"
        style={{
          marginTop: 'var(--mac-spacing-3)',
          padding: 'var(--mac-spacing-3)',
          borderRadius: 'var(--mac-radius-md)',
          background: 'var(--mac-accent-red-bg)',
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-sm)',
        }}
      >
        <AlertCircle style={{ width: 16, height: 16, flexShrink: 0, color: 'var(--mac-accent-red)' }} />
        <span>{error}</span>
      </div>
    ) : null;

  const primaryButton = (label: string, onClick: () => void, disabled: boolean, icon?: ReactNode) => (
    <Button onClick={onClick} disabled={disabled}>
      {loading ? (
        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
      ) : (
        icon
      )}
      {label}
    </Button>
  );

  const backButton = (to: 1 | 2) => (
    <Button onClick={() => setStep(to)} variant="outline" disabled={loading}>
      <ArrowLeft className="w-4 h-4 mr-2" />
      {t('misc.tfsw_back')}
    </Button>
  );

  return (
    <div
      className="mx-auto w-full"
      style={{ maxWidth: 400, padding: '0 var(--mac-spacing-2)', fontFamily: 'inherit' }}
    >
      <div className="flex flex-col items-center text-center" style={{ marginBottom: 'var(--mac-spacing-4)' }}>
        <div
          className="flex items-center justify-center"
          style={{
            width: 44,
            height: 44,
            borderRadius: 'var(--mac-radius-full)',
            background: 'var(--mac-accent-blue-bg)',
            marginBottom: 'var(--mac-spacing-3)',
          }}
        >
          <ShieldCheck style={{ width: 24, height: 24, color: 'var(--mac-accent-blue)' }} />
        </div>
        <h2 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)' as CSSProperties['fontWeight'] }}>
          {t('misc.tfsw2_title')}
        </h2>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="mt-1"
            style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', textDecoration: 'underline', cursor: 'pointer', font: 'inherit' }}
          >
            {t('misc.cancel')}
          </button>
        )}
      </div>

      {step !== 4 && renderStepper()}

      {step === 1 && (
        <div className="flex flex-col" style={{ gap: 'var(--mac-spacing-4)' }}>
          <div className="text-center">
            <h3 style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)' as CSSProperties['fontWeight'], marginBottom: 'var(--mac-spacing-2)' }}>
              {t('misc.tfsw2_step1_title')}
            </h3>
            <p style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
              {t('misc.tfsw2_step1_desc')}
            </p>
          </div>
          <div>
            <label
              htmlFor="tfsw-recovery-email"
              className="block"
              style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)' as CSSProperties['fontWeight'], marginBottom: 'var(--mac-spacing-2)', color: 'var(--mac-text-primary)' }}
            >
              {t('misc.tfsw_label_recovery_email')}
            </label>
            <Input
              id="tfsw-recovery-email"
              type="email"
              aria-label="2FA recovery email"
              value={recoveryEmail}
              onChange={(e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRecoveryEmail(e.target.value)}
              placeholder="recovery@example.com"
            />
          </div>
          {renderError()}
          <div className="flex justify-end">
            {primaryButton(t('misc.tfsw_next'), handleSetup, loading, <ArrowRight className="w-4 h-4 mr-2" />)}
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="flex flex-col" style={{ gap: 'var(--mac-spacing-4)' }}>
          <div className="text-center">
            <h3 style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)' as CSSProperties['fontWeight'], marginBottom: 'var(--mac-spacing-2)' }}>
              {t('misc.tfsw2_step2_title')}
            </h3>
            <p style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
              {t('misc.tfsw_step3_desc_totp')}
            </p>
          </div>
          <div
            className="flex flex-col items-center"
            style={{ padding: 'var(--mac-spacing-4)', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-lg)', background: 'var(--mac-bg-content)' }}
          >
            {qrValue ? (
              <div style={{ padding: 'var(--mac-spacing-3)', background: '#fff', borderRadius: 'var(--mac-radius-md)' }}>
                {/* Контракт: qr_code_url — ГОТОВОЕ PNG-изображение QR (data:image/png;base64),
                    сгенерированное бэкендом из otpauth-URI. otpauth:// на случай смены контракта. */}
                {qrValue.startsWith('data:image') ? (
                  <img src={qrValue} width={176} height={176} alt="QR-код 2FA" style={{ display: 'block' }} />
                ) : (
                  <QRCodeSVG value={qrValue} size={176} level="M" />
                )}
              </div>
            ) : null}
            <div style={{ marginTop: 'var(--mac-spacing-3)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', textAlign: 'center' }}>
              {t('misc.tfsw_or_enter_secret')}
            </div>
            <div className="flex items-center" style={{ gap: 'var(--mac-spacing-2)', marginTop: 'var(--mac-spacing-2)' }}>
              <code
                style={{
                  padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                  background: 'var(--mac-background-tertiary)',
                  borderRadius: 'var(--mac-radius-sm)',
                  fontFamily: 'var(--mac-font-family-mono, monospace)',
                  fontSize: 'var(--mac-font-size-sm)',
                  letterSpacing: '0.08em',
                  wordBreak: 'break-all',
                  maxWidth: 260,
                }}
              >
                {showSecret ? secretKey : '•'.repeat(Math.min(secretKey.length || 16, 32))}
              </code>
              <button
                type="button"
                onClick={() => setShowSecret(!showSecret)}
                aria-label={showSecret ? t('misc.tfsw_aria_hide_secret') : t('misc.tfsw_aria_show_secret')}
                style={{ color: 'var(--mac-text-secondary)', cursor: 'pointer', background: 'transparent', border: 'none', padding: 4 }}
              >
                {showSecret ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
              </button>
              <button
                type="button"
                onClick={() => copyToClipboard(secretKey, 'secret')}
                aria-label={t('misc.tfsw_aria_copy_secret')}
                style={{ color: 'var(--mac-text-secondary)', cursor: 'pointer', background: 'transparent', border: 'none', padding: 4 }}
              >
                <Copy style={{ width: 16, height: 16 }} />
              </button>
              {copied === 'secret' && (
                <span style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-accent-green)' }}>
                  {t('misc.tfsw_copied_to_clipboard')}
                </span>
              )}
            </div>
          </div>
          {renderError()}
          <div className="flex justify-between">
            {backButton(1)}
            {primaryButton(t('misc.tfsw_next'), () => setStep(3), false, <ArrowRight className="w-4 h-4 mr-2" />)}
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="flex flex-col" style={{ gap: 'var(--mac-spacing-4)' }}>
          <div className="text-center">
            <h3 style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)' as CSSProperties['fontWeight'], marginBottom: 'var(--mac-spacing-2)' }}>
              {t('misc.tfsw2_step3_title')}
            </h3>
            <p style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
              {t('misc.tfsw_step3_desc_totp')}
            </p>
          </div>
          <div>
            <label
              htmlFor="tfsw-code"
              className="block text-center"
              style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)' as CSSProperties['fontWeight'], marginBottom: 'var(--mac-spacing-2)' }}
            >
              {t('misc.tfsw_label_verification_code')}
            </label>
            <input
              id="tfsw-code"
              ref={codeRef}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && code.length === 6 && !loading) handleVerify();
              }}
              aria-label="2FA verification code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000"
              maxLength={6}
              className="w-full"
              style={{
                padding: 'var(--mac-spacing-3)',
                textAlign: 'center',
                fontFamily: 'var(--mac-font-family-mono, monospace)',
                fontSize: 'var(--mac-font-size-xl)',
                letterSpacing: '0.5em',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-md)',
                background: 'var(--mac-bg-content)',
                color: 'var(--mac-text-primary)',
                outline: 'none',
              }}
            />
          </div>
          {renderError()}
          <div className="flex justify-between">
            {backButton(2)}
            {primaryButton(t('misc.tfsw_confirm_button'), handleVerify, loading || code.length !== 6, <CheckCircle className="w-4 h-4 mr-2" />)}
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="flex flex-col items-center" style={{ gap: 'var(--mac-spacing-4)' }}>
          <CheckCircle style={{ width: 48, height: 48, color: 'var(--mac-accent-green)' }} />
          <div className="text-center">
            <h3 style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)' as CSSProperties['fontWeight'], marginBottom: 'var(--mac-spacing-2)' }}>
              {t('misc.tfsw_step5_title')}
            </h3>
            <p style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
              {t('misc.tfsw_step5_desc')}
            </p>
          </div>
          {backupCodes.length > 0 && (
            <div
              className="w-full"
              style={{ padding: 'var(--mac-spacing-4)', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-lg)' }}
            >
              <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-2)' }}>
                {t('misc.tfsw_backup_warning')}
              </div>
              <div className="grid grid-cols-2" style={{ gap: 'var(--mac-spacing-2)', marginBottom: 'var(--mac-spacing-3)' }}>
                {backupCodes.map((backupCode, idx) => (
                  <code
                    key={idx}
                    style={{
                      padding: 'var(--mac-spacing-2)',
                      background: 'var(--mac-background-tertiary)',
                      borderRadius: 'var(--mac-radius-sm)',
                      fontFamily: 'var(--mac-font-family-mono, monospace)',
                      fontSize: 'var(--mac-font-size-sm)',
                      textAlign: 'center',
                    }}
                  >
                    {backupCode}
                  </code>
                ))}
              </div>
              <div className="flex" style={{ gap: 'var(--mac-spacing-2)' }}>
                <Button variant="outline" size="small" onClick={() => copyToClipboard(backupCodes.join('\n'), 'codes')}>
                  <Copy className="w-4 h-4 mr-2" />
                  {t('misc.tfsw_copy_all')}
                </Button>
                <Button variant="outline" size="small" onClick={downloadBackupCodes}>
                  <Download className="w-4 h-4 mr-2" />
                  {t('misc.tfsw_download')}
                </Button>
              </div>
            </div>
          )}
          <Button
            onClick={() => {
              // Завершение входа — только после показа резервных кодов
              if (enrolledPayload && onEnrolled) {
                onEnrolled(enrolledPayload);
                return;
              }
              onComplete?.();
            }}
          >
            <CheckCircle className="w-4 h-4 mr-2" />
            {t('misc.tfsw_finish_button')}
          </Button>
        </div>
      )}
    </div>
  );
};

export default TwoFactorSetupWizard;
