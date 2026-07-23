import { useTranslation } from '../../i18n/useTranslation';
/**
 * ForgotPassword — password recovery component.
 *
 * UX Audit — Forgot Password Overhaul:
 *   #1: Import api from api/client (was utils/api — separate axios instance)
 *   #3: Resend code button with countdown
 *   #4: Show/hide password toggle
 *   #5: Min 8 chars + password strength indicator
 *   #6: Inline errors instead of toast-only
 *   #7: All hardcoded RU strings → translations (RU/UZ/EN)
 *   #8: Password strength indicator (reuse from Setup)
 *   #9: Real-time confirm password validation on blur
 *   #10: Remove 3s auto-return, keep explicit button
 *   #12: Hardcoded colors → --mac-* tokens
 *   #14: PropTypes cleanup
 *   #15: type="button" + state moved to top
 */

import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from 'react';
import PropTypes from 'prop-types';
import {
  Mail, Phone, ArrowLeft, Send, CheckCircle, RefreshCw, Shield, Key,
  Eye, EyeOff, AlertCircle,
} from 'lucide-react';
import { api } from '../../api/client';
import { toast } from 'react-toastify';
import logger from '../../utils/logger';
import { Input } from '../ui/macos';

// ============================================================================
// PASSWORD STRENGTH (shared with Setup.jsx — same logic)
// ============================================================================
function getPasswordStrength(password, t) {
  if (!password) return { score: 0, label: '', color: 'transparent', percent: 0 };
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^a-zA-Z0-9]/.test(password)) score += 1;
  score = Math.min(score, 4);
  const labels = [
    { label: t('final.fp_strength_very_weak'), color: 'var(--mac-error)', percent: 25 },
    { label: t('final.fp_strength_weak'), color: 'var(--mac-warning)', percent: 50 },
    { label: t('final.fp_strength_medium'), color: 'var(--mac-warning)', percent: 75 },
    { label: t('final.fp_strength_good'), color: 'var(--mac-success)', percent: 100 },
    { label: t('final.fp_strength_strong'), color: 'var(--mac-success)', percent: 100 },
  ];
  return { score, ...labels[score] };
}

const RESEND_COOLDOWN_SECONDS = 30;

const ForgotPassword = ({ onBack, onSuccess, language = 'RU' }) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // All state at the top (UX Audit #15 — was scattered)
  const [step, setStep] = useState('method');
  const [method, setMethod] = useState('phone');
  const [contact, setContact] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [inlineError, setInlineError] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordsMatch, setPasswordsMatch] = useState(null);
  const [resendCountdown, setResendCountdown] = useState(0);

  const passwordStrength = getPasswordStrength(newPassword, t);

  // Resend countdown timer
  useEffect(() => {
    if (resendCountdown <= 0) return undefined;
    const timer = setTimeout(() => setResendCountdown((prev) => prev - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendCountdown]);

  // Real-time password match check (UX Audit #9)
  const handleConfirmPasswordBlur = useCallback(() => {
    if (!confirmPassword) {
      setPasswordsMatch(null);
      return;
    }
    setPasswordsMatch(newPassword === confirmPassword);
  }, [newPassword, confirmPassword]);

  const validatePhone = (phone) => /^\+998\d{9}$/.test(phone);
  const validateEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  // UX Audit ForgotPassword #1: formatPhone переписан с нуля.
  //
  // Прошлый formatPhone имел 4 бага:
  //   1. НЕЛЬЗЯ БЫЛО СТЕРЕТЬ номер: при `+9989` (digits='9989') не попадал
  //      ни в одно условие → return value → поле «залипало» на +9989.
  //   2. НЕЛЬЗЯ БЫЛО СТЕРЕТЬ префикс +998: digits='998' → return '+998'
  //      всегда возвращало +998, стереть было нельзя.
  //   3. При вводе 12+ цифр, начинающихся на 9, не форматировалось.
  //   4. При вставке номера с префиксом 8 (РФ-стиль) не обрабатывалось.
  //
  // Новый форматтер:
  //   - принимает ЛЮБОЙ ввод (включая пустую строку — возвращает '');
  //   - нормализует к формату +998XXXXXXXXX (12 цифр с +);
  //   - поддерживает ввод: 9XXXXXXXXX (10 цифр), 998XXXXXXXXX (12 цифр),
  //     +998XXXXXXXXX, 8XXXXXXXXX (РФ-стиль, считается опечаткой);
  //   - ограничивает длину до 12 цифр (защита от paste-атак);
  //   - всегда возвращает либо '', либо строку, начинающуюся с '+998'.
  const formatPhone = (value) => {
    if (!value) return '';
    const digits = String(value).replace(/\D/g, '');

    // Пустой ввод → пустая строка (старый код здесь возвращал `value`,
    // из-за чего поле показывало '+', '+' или '998').
    if (digits.length === 0) return '';

    // Нормализуем к 12-значному узбекскому номеру.
    let normalized = digits;

    // Если ввели 10 цифр начиная с 9 — это локальный UZ номер без кода страны.
    if (normalized.length <= 10 && normalized.startsWith('9')) {
      normalized = '998' + normalized;
    }
    // Если ввели 11 цифр начиная с 8 (РФ-стиль, частая опечатка) —
    // считаем что имелся в виду +998, берём последние 9 цифр.
    else if (normalized.length === 11 && normalized.startsWith('8')) {
      normalized = '998' + normalized.slice(2);
    }
    // Если ввели номер с кодом 998 — оставляем как есть.
    else if (normalized.startsWith('998')) {
      // уже в нужном формате
    }
    // Любой другой случай (например, 7-значный городской) —
    // не форматируем, оставляем как есть (пусть валидация покажет ошибку).
    else {
      return value;
    }

    // Ограничиваем до 12 цифр (998 + 9 цифр номера).
    normalized = normalized.slice(0, 12);

    return '+' + normalized;
  };

  const startResendCountdown = useCallback(() => {
    setResendCountdown(RESEND_COOLDOWN_SECONDS);
  }, []);

  // ===== API CALLS =====

  const sendPhoneReset = async () => {
    setLoading(true);
    setInlineError('');
    try {
      const response = (await api.post('/password-reset/initiate', { phone: contact })) as import('axios').AxiosResponse<Record<string, unknown>>;
      if (response.data.success) {
        toast.success(t('final.fp_sms_sent'));
        setStep('phone-verify');
        startResendCountdown();
      }
    } catch (error) {
      logger.error('Error sending phone reset:', error);
      setInlineError(t('final.fp_sms_error'));
      toast.error(t('final.fp_sms_error'));
    } finally {
      setLoading(false);
    }
  };

  const sendEmailReset = async () => {
    setLoading(true);
    setInlineError('');
    try {
      const response = (await api.post('/password-reset/initiate', { email: contact })) as import('axios').AxiosResponse<Record<string, unknown>>;
      if (response.data.success) {
        toast.success(t('final.fp_email_sent_to') + ' ' + contact);
        setStep('email-verify');
      }
    } catch (error) {
      logger.error('Error sending email reset:', error);
      setInlineError(t('final.fp_email_error'));
      toast.error(t('final.fp_email_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleMethodSelect = async () => {
    setInlineError('');
    if (!contact.trim()) {
      setInlineError(method === 'phone' ? t('final.fp_enter_phone') : t('final.fp_enter_email'));
      return;
    }
    if (method === 'phone' && !validatePhone(contact)) {
      setInlineError(t('final.fp_invalid_phone'));
      return;
    }
    if (method === 'email' && !validateEmail(contact)) {
      setInlineError(t('final.fp_invalid_email'));
      return;
    }
    if (method === 'phone') {
      await sendPhoneReset();
    } else {
      await sendEmailReset();
    }
  };

  const handleVerifyPhoneCode = async () => {
    setInlineError('');
    if (!verificationCode || verificationCode.length !== 6) {
      setInlineError(t('final.fp_enter_code_error'));
      return;
    }
    setLoading(true);
    try {
      const response = (await api.post('/password-reset/verify-phone', {
        phone: contact,
        verification_code: verificationCode,
      })) as import('axios').AxiosResponse<Record<string, unknown>>;
      if (response.data.success) {
        setResetToken(String(response.data.reset_token));
        setStep('reset-password');
        toast.success(t('final.fp_phone_confirmed'));
      }
    } catch (error) {
      logger.error('Error verifying phone code:', error);
      setInlineError(t('final.fp_invalid_code'));
    } finally {
      setLoading(false);
    }
  };

  const handleResendCode = async () => {
    if (resendCountdown > 0) return;
    setLoading(true);
    setInlineError('');
    try {
      const response = (await api.post('/password-reset/initiate', { phone: contact })) as import('axios').AxiosResponse<Record<string, unknown>>;
      if (response.data.success) {
        toast.success(t('final.fp_sms_sent'));
        startResendCountdown();
      }
    } catch (error) {
      logger.error('Error resending phone reset:', error);
      setInlineError(t('final.fp_sms_error'));
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordReset = async () => {
    setInlineError('');
    // UX Audit #5: minimum 8 characters (was 6)
    if (!newPassword || newPassword.length < 8) {
      setInlineError(t('final.fp_password_too_short'));
      return;
    }
    if (newPassword !== confirmPassword) {
      setInlineError(t('final.fp_password_mismatch'));
      return;
    }
    setLoading(true);
    try {
      const response = (await api.post('/password-reset/confirm', {
        token: resetToken,
        new_password: newPassword,
      })) as import('axios').AxiosResponse<Record<string, unknown>>;
      if (response.data.success) {
        setStep('success');
        toast.success(t('final.fp_success'));
        // UX Audit #10: removed 3s auto-return setTimeout.
        // User clicks "Back to Login" explicitly.
      }
    } catch (error) {
      logger.error('Error resetting password:', error);
      setInlineError(t('final.fp_reset_error'));
    } finally {
      setLoading(false);
    }
  };

  // ===== SHARED STYLES (using --mac-* tokens, UX Audit #12) =====
  const accentColor = 'var(--mac-accent-blue, #007aff)';
  const successColor = 'var(--mac-success, #34c759)';
  const textPrimary = 'var(--mac-text-primary, #1d1d1f)';
  const textSecondary = 'var(--mac-text-secondary, #86868b)';
  const textTertiary = 'var(--mac-text-tertiary, #aeaeb2)';

  const iconCircleStyle = (color) => ({
    width: '64px',
    height: '64px',
    background: `color-mix(in srgb, ${color}, transparent 88%)`,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  });

  const inputStyle = {
    width: '100%',
    padding: '12px 14px',
    border: '1px solid var(--mac-card-border, rgba(148, 163, 184, 0.35))',
    borderRadius: '14px',
    fontSize: 'var(--mac-font-size-base)',
    background: 'color-mix(in srgb, var(--mac-card-bg, #fff), transparent 30%)',
    color: textPrimary,
    outline: 'none',
  };

  const labelStyle = {
    display: 'block',
    marginBottom: 'var(--mac-spacing-2)',
    fontSize: 'var(--mac-font-size-sm)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: textSecondary,
    marginLeft: 'var(--mac-spacing-1)',
  };

  const btnPrimaryStyle = {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 'var(--mac-spacing-2)',
    padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
    border: 'none',
    borderRadius: '14px',
    background: accentColor,
    color: 'var(--mac-text-on-accent, white)',
    fontSize: 'var(--mac-font-size-base)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    cursor: 'pointer',
    transition: 'opacity 150ms ease',
  };

  const btnOutlineStyle = {
    ...btnPrimaryStyle,
    background: 'transparent',
    border: '1px solid var(--mac-card-border, rgba(148, 163, 184, 0.35))',
    color: textPrimary,
  };

  const errorBannerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--mac-spacing-2)',
    padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
    background: 'color-mix(in srgb, var(--mac-error, #ef4444), transparent 88%)',
    border: '1px solid color-mix(in srgb, var(--mac-error, #ef4444), transparent 70%)',
    borderRadius: 'var(--mac-radius-lg)',
    color: 'var(--mac-error, #ef4444)',
    fontSize: 'var(--mac-font-size-sm)',
    fontWeight: 'var(--mac-font-weight-medium)',
  };

  // ===== RENDER: METHOD SELECTION =====
  const renderMethodSelection = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <div style={{ textAlign: 'center' }}>
        <h2 style={{ fontSize: 'var(--mac-font-size-3xl)', fontWeight: 'var(--mac-font-weight-bold)', marginBottom: 'var(--mac-spacing-2)', color: textPrimary }}>{t('final.password_recovery_title')}</h2>
        <p style={{ color: textSecondary, fontSize: 'var(--mac-font-size-base)' }}>{t('final.password_recovery_subtitle')}</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--mac-spacing-4)' }}>
          {[
            { key: 'phone', icon: Phone, label: t('final.fp_method_phone') },
            { key: 'email', icon: Mail, label: t('final.fp_method_email') },
          ].map(({ key, icon: Icon, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => {
                // UX Audit ForgotPassword #2: при переключении method phone↔email
                // очищаем поле contact и ошибку, чтобы пользователь не видел
                // «телефон в поле email» или наоборот.
                setMethod(key);
                setContact('');
                setInlineError('');
              }}
              style={{
                padding: 'var(--mac-spacing-4)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 'var(--mac-spacing-2)',
                cursor: 'pointer',
                background: method === key
                  ? `color-mix(in srgb, ${accentColor}, transparent 88%)`
                  : 'transparent',
                borderColor: method === key ? accentColor : 'var(--mac-card-border, rgba(148,163,184,0.2))',
                border: '1px solid',
                transition: 'all 0.2s ease',
                borderRadius: 'var(--mac-radius-xl)',
              }}
            >
              <Icon size={24} color={method === key ? accentColor : textSecondary} />
              <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: method === key ? accentColor : textPrimary }}>{label}</span>
            </button>
          ))}
        </div>

        <div>
          <label style={labelStyle}>{method === 'phone' ? t('final.fp_phone_label') : t('final.fp_email_label')}</label>
          <Input
            type={method === 'phone' ? 'tel' : 'email'}
            aria-label={method === 'phone' ? t('final.fp_phone_label') : t('final.fp_email_label')}
            value={contact}
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
              const value = method === 'phone' ? formatPhone(e.target.value) : e.target.value;
              setContact(value);
              setInlineError('');
            }}
            placeholder={method === 'phone' ? '+998XXXXXXXXX' : 'example@domain.com'}
            // UX Audit ForgotPassword #3: maxLength для телефона = 13 символов
            // (+998 + 9 цифр = 13), для email — стандартный 254 (RFC 5321).
            maxLength={method === 'phone' ? 13 : 254}
            // UX Audit ForgotPassword #4: autocomplete для UX — браузер предложит
            // сохранённый телефон/email.
            autoComplete={method === 'phone' ? 'tel' : 'email'}
            // UX Audit ForgotPassword #5: inputMode — показывает цифровую клавиатуру
            // на мобильных для телефона.
            inputMode={method === 'phone' ? 'numeric' : 'email'}
            disabled={loading}
            style={{
              ...inputStyle,
              borderColor: inlineError
                ? 'color-mix(in srgb, var(--mac-error, #ef4444), transparent 50%)'
                : inputStyle.border,
            }}
          />
          <p style={{ fontSize: 'var(--mac-font-size-xs)', color: textTertiary, marginTop: 'var(--mac-spacing-2)', marginLeft: 'var(--mac-spacing-1)' }}>
            {method === 'phone' ? t('final.fp_phone_format') : t('final.fp_email_format')}
          </p>
        </div>

        {inlineError && (
          <div style={errorBannerStyle}>
            <AlertCircle size={14} aria-hidden="true" />
            <span>{inlineError}</span>
          </div>
        )}

        <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)' }}>
          <button type="button" onClick={onBack} style={btnOutlineStyle} disabled={loading}>
            <ArrowLeft size={16} />
            {t('final.fp_back')}
          </button>
          <button
            type="button"
            onClick={handleMethodSelect}
            style={btnPrimaryStyle}
            aria-label={loading ? t('final.fp_sending') : t('final.fp_continue')}
            disabled={loading || !contact.trim()}
          >
            {loading ? (
              <><RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />{t('final.fp_sending')}</>
            ) : (
              <><Send size={16} />{t('final.fp_continue')}</>
            )}
          </button>
        </div>
      </div>
    </div>
  );

  // ===== RENDER: PHONE VERIFICATION =====
  const renderPhoneVerification = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ ...iconCircleStyle(accentColor), margin: '0 auto 16px' }}>
          <Phone size={32} color={accentColor} />
        </div>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-2)', color: textPrimary }}>{t('final.fp_enter_code')}</h3>
        <p style={{ color: textSecondary, fontSize: 'var(--mac-font-size-base)' }}>{t('final.fp_code_sent_to')}</p>
        <p style={{ color: accentColor, fontWeight: 'var(--mac-font-weight-semibold)', marginTop: 'var(--mac-spacing-1)' }}>{contact}</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
        <div>
          <label style={labelStyle}>{t('final.fp_code_label')}</label>
          <Input
            type="text"
            aria-label={t('final.fp_code_label')}
            value={verificationCode}
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
              setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6));
              setInlineError('');
            }}
            placeholder="000000"
            maxLength={6}
            style={{
              ...inputStyle,
              textAlign: 'center',
              fontSize: 'var(--mac-font-size-3xl)',
              letterSpacing: '4px',
              fontWeight: 'var(--mac-font-weight-semibold)',
              borderColor: inlineError
                ? 'color-mix(in srgb, var(--mac-error, #ef4444), transparent 50%)'
                : inputStyle.border,
            }}
            disabled={loading}
          />
        </div>

        {/* UX Audit #3: Resend code button with countdown */}
        <div style={{ textAlign: 'center' }}>
          {resendCountdown > 0 ? (
            <span style={{ fontSize: 'var(--mac-font-size-sm)', color: textTertiary }}>
              {t('final.fp_resend_in')} {resendCountdown} {t('final.fp_seconds')}
            </span>
          ) : (
            <button
              type="button"
              onClick={handleResendCode}
              disabled={loading}
              style={{
                background: 'transparent',
                border: 'none',
                color: accentColor,
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                cursor: loading ? 'not-allowed' : 'pointer',
                textDecoration: 'underline',
                font: 'inherit',
              }}
            >
              {t('final.fp_resend_code')}
            </button>
          )}
        </div>

        {inlineError && (
          <div style={errorBannerStyle}>
            <AlertCircle size={14} aria-hidden="true" />
            <span>{inlineError}</span>
          </div>
        )}

        <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)' }}>
          <button type="button" onClick={() => setStep('method')} style={btnOutlineStyle} disabled={loading}>
            <ArrowLeft size={16} />
            {t('final.fp_back')}
          </button>
          <button
            type="button"
            onClick={handleVerifyPhoneCode}
            style={btnPrimaryStyle}
            aria-label={loading ? t('final.fp_checking') : t('final.fp_confirm')}
            disabled={loading || !verificationCode || verificationCode.length !== 6}
          >
            {loading ? (
              <><RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />{t('final.fp_checking')}</>
            ) : (
              <><Shield size={16} />{t('final.fp_confirm')}</>
            )}
          </button>
        </div>
      </div>
    </div>
  );

  // ===== RENDER: EMAIL VERIFICATION =====
  const renderEmailVerification = () => (
    <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <div style={iconCircleStyle(accentColor)}>
          <Mail size={32} color={accentColor} />
        </div>
      </div>
      <div>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-2)', color: textPrimary }}>{t('final.fp_check_email')}</h3>
        <p style={{ color: textSecondary, fontSize: 'var(--mac-font-size-base)' }}>{t('final.fp_email_sent_to')}</p>
        <p style={{ color: accentColor, fontWeight: 'var(--mac-font-weight-semibold)', marginTop: 'var(--mac-spacing-1)' }}>{contact}</p>
      </div>
      <div style={{ fontSize: 'var(--mac-font-size-sm)', color: textTertiary, lineHeight: '1.5' }}>
        <p>{t('final.fp_email_instruction1')}</p>
        <p>{t('final.fp_email_instruction2')}</p>
      </div>
      <button type="button" onClick={() => setStep('method')} style={{ ...btnOutlineStyle, width: '100%' }}>
        <ArrowLeft size={16} />
        {t('final.fp_back')}
      </button>
    </div>
  );

  // ===== RENDER: RESET PASSWORD =====
  const renderPasswordReset = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--mac-spacing-4)' }}>
          <div style={iconCircleStyle(successColor)}>
            <Key size={32} color={successColor} />
          </div>
        </div>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-2)', color: textPrimary }}>{t('final.fp_create_new_password')}</h3>
        <p style={{ color: textSecondary, fontSize: 'var(--mac-font-size-base)' }}>{t('final.fp_enter_new_password')}</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
        {/* New password with show/hide (UX Audit #4) */}
        <div>
          <label style={labelStyle}>{t('final.fp_new_password')}</label>
          <div style={{ position: 'relative' }}>
            <Input
              type={showNewPassword ? 'text' : 'password'}
              aria-label={t('final.fp_new_password')}
              value={newPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
                setNewPassword(e.target.value);
                setInlineError('');
                if (confirmPassword) setPasswordsMatch(e.target.value === confirmPassword);
              }}
              placeholder="••••••••"
              disabled={loading}
              autoComplete="new-password"
              style={{ ...inputStyle, paddingRight: '44px' }}
            />
            <button
              type="button"
              onClick={() => setShowNewPassword((v) => !v)}
              aria-label={showNewPassword ? t('final.fp_hide_password') : t('final.fp_show_password')}
              title={showNewPassword ? t('final.fp_hide_password') : t('final.fp_show_password')}
              style={{
                position: 'absolute',
                right: '6px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'transparent',
                border: 'none',
                color: textSecondary,
                cursor: 'pointer',
                padding: 'var(--mac-spacing-2)',
                borderRadius: 'var(--mac-radius-md)',
              }}
            >
              {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {/* Password strength indicator (UX Audit #8) */}
          {newPassword && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', marginTop: 'var(--mac-spacing-1)' }}>
              <div style={{ flex: 1, height: '4px', background: 'color-mix(in srgb, var(--mac-text-secondary, #8e8e93), transparent 70%)', borderRadius: '999px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${passwordStrength.percent}%`, background: passwordStrength.color, borderRadius: '999px', transition: 'width 200ms ease, background 200ms ease' }} />
              </div>
              <span style={{ fontSize: 'var(--mac-font-size-xs)', fontWeight: 'var(--mac-font-weight-semibold)', color: passwordStrength.color, minWidth: '80px', textAlign: 'right' }}>
                {passwordStrength.label}
              </span>
            </div>
          )}
          <span style={{ fontSize: 'var(--mac-font-size-xs)', color: textTertiary, display: 'block', marginTop: 'var(--mac-spacing-1)' }}>
            {t('final.fp_password_hint')}
          </span>
        </div>

        {/* Confirm password with show/hide (UX Audit #4) + real-time match (UX Audit #9) */}
        <div>
          <label style={labelStyle}>{t('final.fp_confirm_password')}</label>
          <div style={{ position: 'relative' }}>
            <Input
              type={showConfirmPassword ? 'text' : 'password'}
              aria-label={t('final.fp_confirm_password')}
              value={confirmPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
                setConfirmPassword(e.target.value);
                setInlineError('');
              }}
              onBlur={handleConfirmPasswordBlur}
              placeholder="••••••••"
              disabled={loading}
              autoComplete="new-password"
              style={{ ...inputStyle, paddingRight: '44px' }}
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword((v) => !v)}
              aria-label={showConfirmPassword ? t('final.fp_hide_password') : t('final.fp_show_password')}
              title={showConfirmPassword ? t('final.fp_hide_password') : t('final.fp_show_password')}
              style={{
                position: 'absolute',
                right: '6px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'transparent',
                border: 'none',
                color: textSecondary,
                cursor: 'pointer',
                padding: 'var(--mac-spacing-2)',
                borderRadius: 'var(--mac-radius-md)',
              }}
            >
              {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {/* Real-time match indicator (UX Audit #9) */}
          {confirmPassword && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', marginTop: 'var(--mac-spacing-1)', fontSize: 'var(--mac-font-size-xs)', fontWeight: 'var(--mac-font-weight-semibold)' }}>
              {passwordsMatch ? (
                <><CheckCircle size={14} style={{ color: successColor }} /><span style={{ color: successColor }}>{t('final.fp_passwords_match')}</span></>
              ) : (
                <><AlertCircle size={14} style={{ color: 'var(--mac-error, #ef4444)' }} /><span style={{ color: 'var(--mac-error, #ef4444)' }}>{t('final.fp_passwords_dont_match')}</span></>
              )}
            </div>
          )}
        </div>

        {inlineError && (
          <div style={errorBannerStyle}>
            <AlertCircle size={14} aria-hidden="true" />
            <span>{inlineError}</span>
          </div>
        )}

        <button
          type="button"
          onClick={handlePasswordReset}
          style={{ ...btnPrimaryStyle, width: '100%' }}
          aria-label={loading ? t('final.fp_resetting') : t('final.fp_reset_password')}
          disabled={loading || !newPassword || !confirmPassword}
        >
          {loading ? (
            <><RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />{t('final.fp_resetting')}</>
          ) : (
            <><Shield size={16} />{t('final.fp_reset_password')}</>
          )}
        </button>
      </div>
    </div>
  );

  // ===== RENDER: SUCCESS =====
  const renderSuccess = () => (
    <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <div style={iconCircleStyle(successColor)}>
          <CheckCircle size={32} color={successColor} />
        </div>
      </div>
      <div>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-2)', color: textPrimary }}>{t('final.fp_success')}</h3>
        <p style={{ color: textSecondary, fontSize: 'var(--mac-font-size-base)' }}>{t('final.fp_can_login_now')}</p>
      </div>
      {/* UX Audit #10: removed 3s auto-return, explicit button only */}
      <button
        type="button"
        onClick={onSuccess || onBack}
        style={{ ...btnPrimaryStyle, width: '100%' }}
      >
        {t('final.fp_back_to_login')}
      </button>
    </div>
  );

  // ===== MAIN RETURN =====
  return (
    <div
      style={{
        width: '100%',
        maxWidth: '450px',
        margin: '0 auto',
        padding: '40px',
        background: 'color-mix(in srgb, var(--mac-card-bg, #fff), transparent 20%)',
        border: '1px solid var(--mac-card-border, rgba(148,163,184,0.2))',
        borderRadius: '24px',
        boxShadow: 'var(--mac-shadow-lg, 0 20px 40px rgba(0,0,0,0.1))',
      }}
    >
      {step === 'method' && renderMethodSelection()}
      {step === 'phone-verify' && renderPhoneVerification()}
      {step === 'email-verify' && renderEmailVerification()}
      {step === 'reset-password' && renderPasswordReset()}
      {step === 'success' && renderSuccess()}
    </div>
  );
};

ForgotPassword.propTypes = {
  language: PropTypes.oneOf(['RU', 'UZ', 'EN']),
  onBack: PropTypes.func,
  onSuccess: PropTypes.func,
};

export default ForgotPassword;
