import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { login, me, setToken } from '../api/client';
import { setProfile } from '../stores/auth';
import auth from '../stores/auth.js';
import { ROLE_OPTIONS, getRouteForProfile } from '../constants/routes';
import ForgotPassword from '../components/auth/ForgotPassword';
import SMSEmail2FA from '../components/security/SMSEmail2FA';
import logger from '../utils/logger';
import {
  Lock,
  User,
  Key,
  ArrowLeft,
  Sun,
  Moon,
  Eye,
  EyeOff,
  AlertCircle,
  RefreshCw,
  ChevronDown
} from 'lucide-react';

const translations = {
  RU: {
    title: 'Вход в систему',
    subtitle: 'Войдите в свой аккаунт для продолжения работы',
    selectRole: 'Выбрать роль',
    username: 'Логин',
    password: 'Пароль',
    login: 'Войти',
    loggingIn: 'Входим...',
    forgotPassword: 'Забыли пароль?',
    backToHome: 'На главную',
    note: 'По умолчанию админ создаётся скриптом create_admin.py (admin/admin123).',
    flagUrl: 'https://flagcdn.com/w80/ru.png'
  },
  UZ: {
    title: 'Tizimga kirish',
    subtitle: 'Ishni davom ettirish uchun akkauntingizga kiring',
    selectRole: 'Rolni tanlang',
    username: 'Login',
    password: 'Parol',
    login: 'Kirish',
    loggingIn: 'Kirilmoqda...',
    forgotPassword: 'Parolni unutdingizmi?',
    backToHome: 'Bosh sahifaga',
    note: 'Odatiy holda admin create_admin.py skripti bilan yaratiladi (admin/admin123).',
    flagUrl: 'https://flagcdn.com/w80/uz.png'
  },
  EN: {
    title: 'System Login',
    subtitle: 'Sign in to your account to continue',
    selectRole: 'Select Role',
    username: 'Username',
    password: 'Password',
    login: 'Sign In',
    loggingIn: 'Signing in...',
    forgotPassword: 'Forgot password?',
    backToHome: 'Back to Home',
    note: 'By default, admin is created by create_admin.py script (admin/admin123).',
    flagUrl: 'https://flagcdn.com/w80/gb.png'
  }
};

export default function Login() {
  const roleOptions = ROLE_OPTIONS;

  const [selectedRoleKey, setSelectedRoleKey] = useState('admin');
  const [username, setUsername] = useState('admin@example.com');
  const [password, setPassword] = useState('admin123');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [language, setLanguage] = useState('RU');
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // 2FA состояние
  const [requires2FA, setRequires2FA] = useState(false);
  const [pending2FAToken, setPending2FAToken] = useState('');
  const [twoFAMethod, setTwoFAMethod] = useState('sms');

  // Theme handling
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const systemIsDark = mediaQuery.matches;
    setIsDarkMode(systemIsDark);
    document.documentElement.setAttribute('data-theme', systemIsDark ? 'dark' : 'light');

    const handler = (e) => {
      setIsDarkMode(e.matches);
      document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  const toggleTheme = () => {
    const newMode = !isDarkMode;
    setIsDarkMode(newMode);
    document.documentElement.setAttribute('data-theme', newMode ? 'dark' : 'light');
  };

  const t = translations[language];
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  function onSelectRole(k) {
    setSelectedRoleKey(k);
    const found = roleOptions.find(r => r.key === k);
    if (found) setUsername(found.username);
  }

  async function performLogin(u, p) {
    try {
      const data = await login(u, p);

      // Проверяем, требуется ли 2FA
      if (data?.requires_2fa && data?.pending_2fa_token) {
        setPending2FAToken(data.pending_2fa_token);
        setTwoFAMethod(data.method || 'sms');
        setRequires2FA(true);
        return { requires2FA: true };
      }

      // Проверяем, требуется ли смена пароля
      if (data?.must_change_password) {
        const token = data?.access_token;
        if (token) {
          setToken(token);
        }
        return { mustChangePassword: true, currentPassword: p };
      }

      const token = data?.access_token;
      if (!token) throw new Error('В ответе не найден access_token');
      setToken(token);
      try {
        const profile = await me();
        setProfile(profile);
      } catch (profileError) {
        logger.warn('Не удалось получить профиль:', profileError);
        setProfile(null);
      }
      return { requires2FA: false, mustChangePassword: false };
    } catch (error) {
      logger.error('Login error:', error);
      throw error;
    }
  }

  async function handle2FASuccess(data) {
    const token = data?.access_token;
    if (token) {
      setToken(token);
      try {
        const profile = await me();
        setProfile(profile);
      } catch (profileError) {
        logger.warn('Не удалось получить профиль:', profileError);
        setProfile(null);
      }

      const state = auth.getState ? auth.getState() : { profile: null };
      const profile = state?.profile || null;
      const computedRoute = getRouteForProfile(profile);
      navigate(computedRoute, { replace: true });
    }
    setRequires2FA(false);
    setPending2FAToken('');
  }

  function handle2FACancel() {
    setRequires2FA(false);
    setPending2FAToken('');
    setErr('');
  }

  function isProtectedPanelPath(pathname) {
    const prefixes = [
      '/admin', '/registrar-panel', '/doctor-panel', '/lab-panel', '/cashier-panel',
      '/cardiologist', '/dermatologist', '/dentist'
    ];
    return prefixes.some(p => pathname === p || pathname.startsWith(p + '/'));
  }

  async function onLoginClick(e) {
    e?.preventDefault?.();
    if (busy) return;
    setBusy(true);
    setErr('');
    try {
      const result = await performLogin(username, password);

      // Если требуется 2FA, не продолжаем навигацию
      if (result?.requires2FA) {
        setBusy(false);
        return;
      }

      // Если требуется смена пароля, перенаправляем на страницу смены пароля
      if (result?.mustChangePassword) {
        setBusy(false);
        navigate('/change-password-required', {
          state: { currentPassword: result.currentPassword },
          replace: true
        });
        return;
      }

      await new Promise(resolve => setTimeout(resolve, 100));

      const state = auth.getState ? auth.getState() : { profile: null };
      const profile = state?.profile || null;
      const computedRoute = getRouteForProfile(profile);
      const fromClean = from || '/';

      let target = computedRoute;
      if (fromClean && fromClean !== '/' && fromClean !== '/login') {
        if (isProtectedPanelPath(fromClean)) {
          if (fromClean === computedRoute) target = fromClean;
        } else {
          target = fromClean;
        }
      }
      navigate(target, { replace: true });
    } catch (e2) {
      const errorMessage = e2?.normalizedMessage || e2?.message || 'Ошибка входа';
      setErr(errorMessage);
    } finally {
      setBusy(false);
    }
  }

  const handleLanguageSwitch = () => {
    const langs = ['RU', 'UZ', 'EN'];
    const currentIndex = langs.indexOf(language);
    const nextIndex = (currentIndex + 1) % langs.length;
    setLanguage(langs[nextIndex]);
  };

  // Экран 2FA верификации
  if (requires2FA) {
    return (
      <div className="landing-container">
        <div className="noise-overlay" />
        <div className="mesh-background" />

        <div style={{ position: 'relative', zIndex: 10, width: '100%', maxWidth: '500px' }}>
          <button
            onClick={handle2FACancel}
            className="btn-premium btn-glass"
            style={{ marginBottom: '24px', padding: '12px 24px' }}
          >
            <ArrowLeft size={18} />
            Назад к входу
          </button>

          <div style={{ animation: 'fadeIn 0.3s ease-out' }}>
            <SMSEmail2FA
              method={twoFAMethod}
              pendingToken={pending2FAToken}
              onSuccess={handle2FASuccess}
              onCancel={handle2FACancel}
            />
          </div>
        </div>
      </div>
    );
  }

  if (showForgotPassword) {
    return (
      <div className="landing-container">
        <div className="noise-overlay" />
        <div className="mesh-background" />

        <div style={{ position: 'relative', zIndex: 10, width: '100%', maxWidth: '500px' }}>
          <button
            onClick={() => setShowForgotPassword(false)}
            className="btn-premium btn-glass"
            style={{ marginBottom: '24px', padding: '12px 24px' }}
          >
            <ArrowLeft size={18} />
            {t.backToHome}
          </button>

          {/* Removed glass-panel wrapper to avoid double card effect */}
          <div style={{ animation: 'fadeIn 0.3s ease-out' }}>
            <ForgotPassword
              language={language}
              onBack={() => setShowForgotPassword(false)}
              onSuccess={() => {
                setShowForgotPassword(false);
                setErr('');
              }}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="landing-container">
      <div className="noise-overlay" />
      <div className="mesh-background" />

      {/* Top Bar */}
      <div style={{
        position: 'absolute',
        top: '24px',
        left: '24px',
        right: '24px',
        display: 'flex',
        justifyContent: 'space-between',
        zIndex: 20
      }}>
        <button
          onClick={() => navigate('/')}
          className="btn-premium btn-glass"
          style={{ padding: '10px 20px', fontSize: '14px', borderRadius: '16px' }}
        >
          <ArrowLeft size={16} />
          {t.backToHome}
        </button>

        <div className="glass-panel" style={{ padding: '8px 16px', borderRadius: '20px', display: 'flex', gap: '16px', alignItems: 'center' }}>
          <button
            onClick={toggleTheme}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--mac-text-primary)', display: 'flex', alignItems: 'center' }}
            aria-label="Toggle theme"
          >
            {isDarkMode ? <Moon size={20} /> : <Sun size={20} />}
          </button>
          <div style={{ width: '1px', height: '20px', background: 'var(--glass-border)' }} />
          <button
            onClick={handleLanguageSwitch}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, borderRadius: '50%', overflow: 'hidden', width: '24px', height: '24px' }}
            aria-label="Switch language"
          >
            <img src={t.flagUrl} alt={language} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </button>
        </div>
      </div>

      {/* Login Card */}
      <div className="glass-panel spotlight-card" style={{
        width: '100%',
        maxWidth: '420px',
        padding: '48px',
        position: 'relative',
        zIndex: 10,
        animation: 'fadeIn 0.5s ease-out'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            width: '64px',
            height: '64px',
            background: 'rgba(0, 122, 255, 0.1)',
            borderRadius: '24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px',
            color: '#007aff',
            boxShadow: '0 0 20px rgba(0, 122, 255, 0.2)'
          }}>
            <Lock size={32} />
          </div>
          <h1 style={{
            fontSize: '32px',
            fontWeight: '800',
            marginBottom: '12px',
            background: 'linear-gradient(135deg, var(--mac-text-primary) 30%, var(--mac-text-secondary) 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            {t.title}
          </h1>
          <p style={{ color: 'var(--mac-text-secondary)', fontSize: '16px', lineHeight: '1.5' }}>
            {t.subtitle}
          </p>
        </div>

        {err && (
          <div className="status-message status-error">
            <AlertCircle size={18} />
            {err}
          </div>
        )}

        <form onSubmit={onLoginClick}>
          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: 600, color: 'var(--mac-text-secondary)', marginLeft: '4px' }}>
              {t.selectRole.toUpperCase()}
            </label>
            <div style={{ position: 'relative' }}>
              <User size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--mac-text-secondary)', pointerEvents: 'none' }} />
              <select
                value={selectedRoleKey}
                onChange={(e) => onSelectRole(e.target.value)}
                disabled={busy}
                className="glass-input"
                style={{ paddingLeft: '44px', paddingRight: '40px', appearance: 'none', cursor: 'pointer' }}
              >
                {roleOptions.map((opt) => (
                  <option key={opt.key} value={opt.key} style={{ color: 'black' }}>{opt.label}</option>
                ))}
              </select>
              <ChevronDown size={16} style={{ position: 'absolute', right: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--mac-text-secondary)', pointerEvents: 'none' }} />
            </div>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: 600, color: 'var(--mac-text-secondary)', marginLeft: '4px' }}>
              {t.username.toUpperCase()}
            </label>
            <div style={{ position: 'relative' }}>
              <User size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--mac-text-secondary)' }} />
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="glass-input"
                style={{ paddingLeft: '44px', opacity: 0.7 }}
                disabled
                readOnly
              />
            </div>
          </div>

          <div style={{ marginBottom: '32px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: 600, color: 'var(--mac-text-secondary)', marginLeft: '4px' }}>
              {t.password.toUpperCase()}
            </label>
            <div style={{ position: 'relative' }}>
              <Key size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--mac-text-secondary)' }} />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="glass-input"
                style={{ paddingLeft: '44px', paddingRight: '44px' }}
                disabled={busy}
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--mac-text-secondary)',
                  padding: '4px'
                }}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={busy}
            className="btn-premium btn-primary"
            style={{ width: '100%', justifyContent: 'center', marginBottom: '20px' }}
          >
            {busy ? (
              <>
                <RefreshCw size={20} className="spin" />
                {t.loggingIn}
              </>
            ) : (
              <>
                {t.login}
                <ArrowLeft size={18} style={{ transform: 'rotate(180deg)' }} />
              </>
            )}
          </button>

          <div style={{ textAlign: 'center' }}>
            <button
              onClick={(e) => { e.preventDefault(); setShowForgotPassword(true); }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--mac-text-secondary)',
                fontSize: '14px',
                cursor: 'pointer',
                textDecoration: 'underline',
                opacity: 0.8
              }}
            >
              {t.forgotPassword}
            </button>
          </div>
        </form>

        <div className="info-panel" style={{ marginTop: '32px', textAlign: 'center' }}>
          💡 {t.note}
        </div>
      </div>
    </div>
  );
}
