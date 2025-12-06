import React, { useState } from 'react';
import {
  Mail,
  Phone,
  ArrowLeft,
  Send,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Shield,
  Key
} from 'lucide-react';
import { api } from '../../utils/api';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
const ForgotPassword = ({ onBack, onSuccess, language = 'RU' }) => {
  const [step, setStep] = useState('method'); // method, phone-verify, email-verify, reset-password
  const [method, setMethod] = useState('phone'); // phone, email
  const [contact, setContact] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const translations = {
    RU: {
      title: 'Восстановление пароля',
      subtitle: 'Выберите способ восстановления пароля',
      methodPhone: 'По номеру телефона',
      methodEmail: 'По электронной почте',
      phoneLabel: 'Номер телефона',
      emailLabel: 'Email адрес',
      continue: 'Продолжить',
      back: 'Назад',
      sending: 'Отправка...',
      newPassword: 'Новый пароль',
      confirmPassword: 'Подтвердите пароль',
      resetPassword: 'Сбросить пароль',
      resetting: 'Сброс...',
      success: 'Пароль успешно изменен!',
      backToLogin: 'Вернуться к входу',
      enterPhone: 'Введите номер телефона',
      enterEmail: 'Введите email адрес',
      phoneFormat: 'Формат: +998XXXXXXXXX',
      emailFormat: 'Формат: example@domain.com',
      passwordMismatch: 'Пароли не совпадают',
      passwordTooShort: 'Пароль должен содержать минимум 6 символов',
      invalidPhone: 'Неверный формат номера телефона',
      invalidEmail: 'Неверный формат email адреса'
    },
    UZ: {
      title: 'Parolni tiklash',
      subtitle: 'Parolni tiklash usulini tanlang',
      methodPhone: 'Telefon raqami orqali',
      methodEmail: 'Email orqali',
      phoneLabel: 'Telefon raqami',
      emailLabel: 'Email manzil',
      continue: 'Davom etish',
      back: 'Orqaga',
      sending: 'Yuborilmoqda...',
      newPassword: 'Yangi parol',
      confirmPassword: 'Parolni tasdiqlang',
      resetPassword: 'Parolni tiklash',
      resetting: 'Tiklanmoqda...',
      success: 'Parol muvaffaqiyatli o\'zgartirildi!',
      backToLogin: 'Kirishga qaytish',
      enterPhone: 'Telefon raqamini kiriting',
      enterEmail: 'Email manzilni kiriting',
      phoneFormat: 'Format: +998XXXXXXXXX',
      emailFormat: 'Format: example@domain.com',
      passwordMismatch: 'Parollar mos kelmaydi',
      passwordTooShort: 'Parol kamida 6 ta belgidan iborat bo\'lishi kerak',
      invalidPhone: 'Telefon raqami formati noto\'g\'ri',
      invalidEmail: 'Email manzil formati noto\'g\'ri'
    },
    EN: {
      title: 'Password Recovery',
      subtitle: 'Choose password recovery method',
      methodPhone: 'By phone number',
      methodEmail: 'By email address',
      phoneLabel: 'Phone number',
      emailLabel: 'Email address',
      continue: 'Continue',
      back: 'Back',
      sending: 'Sending...',
      newPassword: 'New password',
      confirmPassword: 'Confirm password',
      resetPassword: 'Reset Password',
      resetting: 'Resetting...',
      success: 'Password successfully changed!',
      backToLogin: 'Back to Login',
      enterPhone: 'Enter phone number',
      enterEmail: 'Enter email address',
      phoneFormat: 'Format: +998XXXXXXXXX',
      emailFormat: 'Format: example@domain.com',
      passwordMismatch: 'Passwords do not match',
      passwordTooShort: 'Password must be at least 6 characters',
      invalidPhone: 'Invalid phone number format',
      invalidEmail: 'Invalid email address format'
    }
  };

  const t = translations[language];

  const validatePhone = (phone) => {
    const phoneRegex = /^\+998\d{9}$/;
    return phoneRegex.test(phone);
  };

  const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const formatPhone = (value) => {
    const digits = value.replace(/\D/g, '');
    if (digits.startsWith('9') && digits.length <= 9) {
      return `+998${digits}`;
    }
    if (digits.startsWith('998')) {
      return `+${digits}`;
    }
    return value;
  };

  const handleMethodSelect = async () => {
    if (!contact.trim()) {
      toast.error(method === 'phone' ? t.enterPhone : t.enterEmail);
      return;
    }

    if (method === 'phone' && !validatePhone(contact)) {
      toast.error(t.invalidPhone);
      return;
    }

    if (method === 'email' && !validateEmail(contact)) {
      toast.error(t.invalidEmail);
      return;
    }

    if (method === 'phone') {
      await sendPhoneReset();
    } else {
      await sendEmailReset();
    }
  };

  const sendPhoneReset = async () => {
    setLoading(true);
    try {
      const response = await api.post('/password-reset/initiate', {
        phone: contact
      });

      if (response.data.success) {
        toast.success('Код для сброса пароля отправлен на ваш номер');
        setStep('phone-verify');
      }
    } catch (error) {
      logger.error('Error sending phone reset:', error);
      toast.error('Ошибка отправки SMS для сброса пароля');
    } finally {
      setLoading(false);
    }
  };

  const sendEmailReset = async () => {
    setLoading(true);
    try {
      const response = await api.post('/password-reset/initiate', {
        email: contact
      });

      if (response.data.success) {
        toast.success('Ссылка для сброса пароля отправлена на email');
        setStep('email-verify');
      }
    } catch (error) {
      logger.error('Error sending email reset:', error);
      toast.error('Ошибка отправки email для сброса пароля');
    } finally {
      setLoading(false);
    }
  };

  const [verificationCode, setVerificationCode] = useState('');

  const handleVerifyPhoneCode = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      toast.error('Введите 6-значный код');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/password-reset/verify-phone', {
        phone: contact,
        verification_code: verificationCode
      });

      if (response.data.success) {
        setResetToken(response.data.reset_token);
        setStep('reset-password');
        toast.success('Телефон подтвержден. Теперь введите новый пароль');
      }
    } catch (error) {
      logger.error('Error verifying phone code:', error);
      toast.error('Неверный код или код истек');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordReset = async () => {
    if (!newPassword || newPassword.length < 6) {
      toast.error(t.passwordTooShort);
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error(t.passwordMismatch);
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/password-reset/confirm', {
        token: resetToken,
        new_password: newPassword
      });

      if (response.data.success) {
        setStep('success');
        toast.success(t.success);

        // Автоматически вернуться к логину через 3 секунды
        setTimeout(() => {
          if (onSuccess) {
            onSuccess();
          }
        }, 3000);
      }
    } catch (error) {
      logger.error('Error resetting password:', error);
      toast.error('Ошибка сброса пароля');
    } finally {
      setLoading(false);
    }
  };

  const renderMethodSelection = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ textAlign: 'center' }}>
        <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '8px', color: 'var(--mac-text-primary)' }}>{t.title}</h2>
        <p style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>{t.subtitle}</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <button
            onClick={() => setMethod('phone')}
            className="glass-panel"
            style={{
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              cursor: 'pointer',
              background: method === 'phone' ? 'rgba(0, 122, 255, 0.1)' : 'transparent',
              borderColor: method === 'phone' ? '#007aff' : 'var(--glass-border)',
              transition: 'all 0.2s ease',
              borderRadius: '16px'
            }}
          >
            <Phone size={24} color={method === 'phone' ? '#007aff' : 'var(--mac-text-secondary)'} />
            <span style={{ fontSize: '13px', fontWeight: '500', color: method === 'phone' ? '#007aff' : 'var(--mac-text-primary)' }}>{t.methodPhone}</span>
          </button>

          <button
            onClick={() => setMethod('email')}
            className="glass-panel"
            style={{
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              cursor: 'pointer',
              background: method === 'email' ? 'rgba(0, 122, 255, 0.1)' : 'transparent',
              borderColor: method === 'email' ? '#007aff' : 'var(--glass-border)',
              transition: 'all 0.2s ease',
              borderRadius: '16px'
            }}
          >
            <Mail size={24} color={method === 'email' ? '#007aff' : 'var(--mac-text-secondary)'} />
            <span style={{ fontSize: '13px', fontWeight: '500', color: method === 'email' ? '#007aff' : 'var(--mac-text-primary)' }}>{t.methodEmail}</span>
          </button>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: '600', color: 'var(--mac-text-secondary)', marginLeft: '4px' }}>
            {method === 'phone' ? t.phoneLabel : t.emailLabel}
          </label>
          <input
            type={method === 'phone' ? 'tel' : 'email'}
            value={contact}
            onChange={(e) => {
              const value = method === 'phone' ? formatPhone(e.target.value) : e.target.value;
              setContact(value);
            }}
            placeholder={method === 'phone' ? '+998XXXXXXXXX' : 'example@domain.com'}
            disabled={loading}
            className="glass-input"
          />
          <p style={{ fontSize: '12px', color: 'var(--mac-text-tertiary)', marginTop: '6px', marginLeft: '4px' }}>
            {method === 'phone' ? t.phoneFormat : t.emailFormat}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={onBack}
            className="btn-premium btn-glass"
            style={{ flex: 1, justifyContent: 'center' }}
            disabled={loading}
          >
            <ArrowLeft size={16} />
            {t.back}
          </button>

          <button
            onClick={handleMethodSelect}
            className="btn-premium btn-primary"
            style={{ flex: 1, justifyContent: 'center' }}
            disabled={loading || !contact.trim()}
          >
            {loading ? (
              <>
                <RefreshCw size={16} className="spin" />
                {t.sending}
              </>
            ) : (
              <>
                <Send size={16} />
                {t.continue}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );

  const renderPhoneVerification = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: '64px', height: '64px', background: 'rgba(0, 122, 255, 0.1)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
          <Phone size={32} color="#007aff" />
        </div>
        <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '8px', color: 'var(--mac-text-primary)' }}>Введите код подтверждения</h3>
        <p style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
          Код отправлен на номер:
        </p>
        <p style={{ color: '#007aff', fontWeight: '600', marginTop: '4px' }}>{contact}</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: '600', color: 'var(--mac-text-secondary)', marginLeft: '4px' }}>Код подтверждения</label>
          <input
            type="text"
            value={verificationCode}
            onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="000000"
            maxLength={6}
            className="glass-input"
            style={{ textAlign: 'center', fontSize: '24px', letterSpacing: '4px', fontWeight: '600' }}
            disabled={loading}
          />
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={() => setStep('method')}
            className="btn-premium btn-glass"
            style={{ flex: 1, justifyContent: 'center' }}
            disabled={loading}
          >
            <ArrowLeft size={16} />
            {t.back}
          </button>

          <button
            onClick={handleVerifyPhoneCode}
            className="btn-premium btn-primary"
            style={{ flex: 1, justifyContent: 'center' }}
            disabled={loading || !verificationCode || verificationCode.length !== 6}
          >
            {loading ? (
              <>
                <RefreshCw size={16} className="spin" />
                Проверка...
              </>
            ) : (
              <>
                <Shield size={16} />
                Подтвердить
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );

  const renderEmailVerification = () => (
    <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <div style={{ width: '64px', height: '64px', background: 'rgba(0, 122, 255, 0.1)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Mail size={32} color="#007aff" />
        </div>
      </div>

      <div>
        <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '8px', color: 'var(--mac-text-primary)' }}>Проверьте ваш email</h3>
        <p style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
          Мы отправили ссылку для сброса пароля на адрес:
        </p>
        <p style={{ color: '#007aff', fontWeight: '600', marginTop: '4px' }}>{contact}</p>
      </div>

      <div style={{ fontSize: '13px', color: 'var(--mac-text-tertiary)', lineHeight: '1.5' }}>
        <p>Перейдите по ссылке в письме для сброса пароля.</p>
        <p>Если письмо не пришло, проверьте папку "Спам".</p>
      </div>

      <button
        onClick={() => setStep('method')}
        className="btn-premium btn-glass"
        style={{ width: '100%', justifyContent: 'center' }}
      >
        <ArrowLeft size={16} />
        {t.back}
      </button>
    </div>
  );

  const renderPasswordReset = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px' }}>
          <div style={{ width: '64px', height: '64px', background: 'rgba(52, 199, 89, 0.1)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Key size={32} color="#34c759" />
          </div>
        </div>
        <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '8px', color: 'var(--mac-text-primary)' }}>Создайте новый пароль</h3>
        <p style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>Введите новый пароль для вашего аккаунта</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: '600', color: 'var(--mac-text-secondary)', marginLeft: '4px' }}>{t.newPassword}</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
            className="glass-input"
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: '600', color: 'var(--mac-text-secondary)', marginLeft: '4px' }}>{t.confirmPassword}</label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
            className="glass-input"
          />
        </div>

        <button
          onClick={handlePasswordReset}
          className="btn-premium btn-primary"
          style={{ width: '100%', justifyContent: 'center' }}
          disabled={loading || !newPassword || !confirmPassword}
        >
          {loading ? (
            <>
              <RefreshCw size={16} className="spin" />
              {t.resetting}
            </>
          ) : (
            <>
              <Shield size={16} />
              {t.resetPassword}
            </>
          )}
        </button>
      </div>
    </div>
  );

  const renderSuccess = () => (
    <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <div style={{ width: '64px', height: '64px', background: 'rgba(52, 199, 89, 0.1)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <CheckCircle size={32} color="#34c759" />
        </div>
      </div>

      <div>
        <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '8px', color: 'var(--mac-text-primary)' }}>{t.success}</h3>
        <p style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
          Теперь вы можете войти в систему с новым паролем
        </p>
      </div>

      <button
        onClick={onSuccess || onBack}
        className="btn-premium btn-primary"
        style={{ width: '100%', justifyContent: 'center' }}
      >
        {t.backToLogin}
      </button>
    </div>
  );

  return (
    <div className="glass-panel spotlight-card" style={{ width: '100%', maxWidth: '450px', margin: '0 auto', padding: '40px' }}>
      {step === 'method' && renderMethodSelection()}
      {step === 'phone-verify' && renderPhoneVerification()}
      {step === 'email-verify' && renderEmailVerification()}
      {step === 'reset-password' && renderPasswordReset()}
      {step === 'success' && renderSuccess()}
    </div>
  );
};

export default ForgotPassword;
