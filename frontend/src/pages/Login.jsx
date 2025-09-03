import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getApiBase, api } from '../api/client';
import { setToken, setProfile } from '../stores/auth';
import auth from '../stores/auth.js';
import { useTheme } from '../contexts/ThemeContext';

/**
 * Логин по OAuth2 Password (FastAPI):
 * POST /login с application/x-www-form-urlencoded полями:
 *   username, password, grant_type=password, scope, client_id, client_secret
 */
export default function Login() {
  const roleOptions = [
    { key: 'admin', label: 'Администратор', username: 'admin', route: '/admin' },
    { key: 'registrar', label: 'Регистратура', username: 'registrar', route: '/registrar-panel' },
    { key: 'lab', label: 'Лаборатория', username: 'lab', route: '/lab-panel' },
    { key: 'doctor', label: 'Врач', username: 'doctor', route: '/doctor-panel' },
    { key: 'cashier', label: 'Касса', username: 'cashier', route: '/cashier-panel' },
    { key: 'cardio', label: 'Кардиолог', username: 'cardio', route: '/cardiologist' },
    { key: 'derma', label: 'Дерматолог', username: 'derma', route: '/dermatologist' },
    { key: 'dentist', label: 'Стоматолог', username: 'dentist', route: '/dentist' },
  ];

  const [selectedRoleKey, setSelectedRoleKey] = useState('admin');
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [language, setLanguage] = useState('RU');

  // Используем централизованную систему темизации
  const { 
    theme, 
    isDark, 
    isLight, 
    toggleTheme, 
    getColor, 
    getSpacing, 
    getFontSize 
  } = useTheme();

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
      rememberMe: 'Запомнить меня',
      backToHome: 'На главную',
      note: 'По умолчанию админ создаётся скриптом create_admin.py (admin/admin123).'
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
      rememberMe: 'Meni eslab qol',
      backToHome: 'Bosh sahifaga',
      note: 'Odatiy holda admin create_admin.py skripti bilan yaratiladi (admin/admin123).'
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
      rememberMe: 'Remember me',
      backToHome: 'Back to Home',
      note: 'By default, admin is created by create_admin.py script (admin/admin123).'
    }
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
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: u, password: p, grant_type: 'password' }).toString(),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      const data = await response.json();
      const token = data?.access_token;
      if (!token) throw new Error('В ответе не найден access_token');
      setToken(token);
      try {
        const meRes = await fetch('/api/v1/auth/me', { headers: { Authorization: `Bearer ${token}` } });
        if (meRes.ok) setProfile(await meRes.json()); else setProfile(null);
      } catch {
        // Игнорируем ошибки получения профиля
        setProfile(null);
      }
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  }

  function pickRouteForRoleCached(defaultPath) {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return defaultPath;
      
      // ВАЖНО: Получаем роль из актуального профиля после логина
      // Не полагаемся на кэшированный профиль, который может быть устаревшим
      const state = auth.getState ? auth.getState() : { profile: null };
      const role = String(state?.profile?.role || '').toLowerCase();
      
      // Логируем для отладки
      console.log('pickRouteForRoleCached: role =', role, 'profile =', state?.profile);
      
      if (role === 'admin') return '/admin';
      if (role === 'registrar') return '/registrar-panel';
      if (role === 'lab') return '/lab-panel';
      if (role === 'doctor') return '/doctor-panel';
      if (role === 'cashier') return '/cashier-panel';
      if (role === 'cardio') return '/cardiologist';
      if (role === 'derma') return '/dermatologist';
      if (role === 'dentist') return '/dentist';
      return '/search';
    } catch (error) {
      console.error('pickRouteForRoleCached error:', error);
      return defaultPath;
    }
  }

  function roleToRoute(roleLower) {
    switch (roleLower) {
      case 'admin': return '/admin';
      case 'registrar': return '/registrar-panel';
      case 'lab': return '/lab-panel';
      case 'doctor': return '/doctor-panel';
      case 'cashier': return '/cashier-panel';
      case 'cardio': return '/cardiologist';
      case 'derma': return '/dermatologist';
      case 'dentist': return '/dentist';
      default: return '/search';
    }
  }

  function resolveRouteFromProfile(profile) {
    if (!profile) return '/search';
    const rolesArr = Array.isArray(profile.roles) ? profile.roles.map(r => String(r).toLowerCase()) : [];
    const roleLower = String(profile.role || profile.role_name || '').toLowerCase();
    if (rolesArr.includes('admin') || roleLower === 'admin') return '/admin';
    if (roleLower) return roleToRoute(roleLower);
    for (const r of rolesArr) {
      const route = roleToRoute(r);
      if (route && route !== '/search') return route;
    }
    return '/search';
  }

  function isProtectedPanelPath(pathname) {
    const prefixes = [
      '/admin','/registrar-panel','/doctor-panel','/lab-panel','/cashier-panel',
      '/cardiologist','/dermatologist','/dentist'
    ];
    return prefixes.some(p => pathname === p || pathname.startsWith(p + '/'));
  }

  async function onLoginClick(e) {
    e?.preventDefault?.();
    if (busy) return;
    setBusy(true);
    setErr('');
    try {
      await performLogin(username, password);

      // Небольшая задержка для обновления профиля в auth store
      await new Promise(resolve => setTimeout(resolve, 100));

      const state = auth.getState ? auth.getState() : { profile: null };
      const profile = state?.profile || null;
      const computedRoute = resolveRouteFromProfile(profile);
      const fromClean = from || '/';

      // Если from ведёт на другой защищённый раздел панели — игнорируем его
      let target = computedRoute;
      if (fromClean && fromClean !== '/' && fromClean !== '/login') {
        if (isProtectedPanelPath(fromClean)) {
          if (fromClean === computedRoute) target = fromClean;
        } else {
          // Нефреймовый/просмотровый маршрут (детали визита и т.п.) — разрешаем возврат
          target = fromClean;
        }
      }

      console.log('Login redirect:', { from: fromClean, computedRoute, target, profile });
      navigate(target, { replace: true });
    } catch (e2) {
      setErr(e2?.message || 'Ошибка входа');
    } finally {
      setBusy(false);
    }
  }

  const textColor = isLight ? getColor('secondary', 700) : getColor('secondary', 200);

  const pageStyle = {
    minHeight: '100vh',
    background: isLight 
      ? `linear-gradient(135deg, ${getColor('primary', 50)} 0%, ${getColor('secondary', 50)} 100%)`
      : `linear-gradient(135deg, ${getColor('secondary', 900)} 0%, ${getColor('secondary', 800)} 100%)`,
    padding: getSpacing('lg'),
    fontFamily: 'system-ui, -apple-system, sans-serif',
    color: textColor,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center'
  };

  const cardStyle = {
    background: theme === 'light' 
      ? 'rgba(255, 255, 255, 0.9)' 
      : 'rgba(15, 23, 42, 0.9)',
    border: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRadius: '20px',
    padding: getSpacing('2xl'),
    boxShadow: theme === 'light' 
      ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
      : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
    backdropFilter: 'blur(10px)',
    maxWidth: '450px',
    width: '100%'
  };

  const buttonStyle = {
    padding: `${getSpacing('md')} ${getSpacing('lg')}`,
    background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'white',
    border: 'none',
    borderRadius: '12px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: '600',
    transition: 'all 0.3s ease',
    boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
    width: '100%',
    disabled: busy
  };

  const buttonSecondaryStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    background: 'transparent',
    color: textColor,
    border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 600)}`,
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '14px',
    transition: 'all 0.3s ease',
    textDecoration: 'none',
    display: 'inline-block',
    textAlign: 'center'
  };

  const inputStyle = {
    width: '100%',
    padding: `${getSpacing('md')} ${getSpacing('md')}`,
    border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 600)}`,
    borderRadius: '12px',
    fontSize: '16px',
    background: theme === 'light' ? 'white' : getColor('gray', 800),
    color: textColor,
    outline: 'none',
    transition: 'all 0.3s ease',
    boxSizing: 'border-box'
  };

  const labelStyle = {
    display: 'block',
    marginBottom: getSpacing('xs'),
    fontWeight: '500',
    fontSize: '14px',
    color: textColor
  };

  const errorStyle = {
    color: getColor('danger', 600),
    background: theme === 'light' ? '#fee2e2' : 'rgba(239, 68, 68, 0.1)',
    border: `1px solid ${getColor('danger', 500)}`,
    borderRadius: '8px',
    padding: getSpacing('sm'),
    marginBottom: getSpacing('md'),
    fontSize: '14px'
  };

  const toggleButtonStyle = {
    padding: getSpacing('xs'),
    background: 'transparent',
    border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 600)}`,
    borderRadius: '8px',
    cursor: 'pointer',
    color: textColor,
    marginLeft: getSpacing('sm')
  };

  const headerStyle = {
    fontSize: '32px',
    fontWeight: '800',
    marginBottom: getSpacing('sm'),
    background: `linear-gradient(135deg, ${getColor('primary', 600)} 0%, ${getColor('primary', 400)} 100%)`,
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    textAlign: 'center'
  };

  const subtitleStyle = {
    fontSize: '16px',
    opacity: 0.8,
    marginBottom: getSpacing('xl'),
    textAlign: 'center',
    lineHeight: '1.5'
  };

  return (
    <div style={pageStyle}>
      {/* Переключатели темы и языка */}
      <div style={{ position: 'absolute', top: getSpacing('lg'), right: getSpacing('lg'), display: 'flex', alignItems: 'center' }}>
        <button 
          onClick={() => toggleTheme()}
          style={toggleButtonStyle}
          title="Переключить тему"
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
        <select 
          value={language} 
          onChange={(e) => setLanguage(e.target.value)}
          style={{
            ...toggleButtonStyle,
            marginLeft: getSpacing('sm'),
            background: theme === 'light' ? 'white' : getColor('gray', 800)
          }}
        >
          <option value="RU">RU</option>
          <option value="UZ">UZ</option>
          <option value="EN">EN</option>
        </select>
      </div>

      {/* Кнопка "На главную" */}
      <div style={{ position: 'absolute', top: getSpacing('lg'), left: getSpacing('lg') }}>
        <button 
          onClick={() => navigate('/')} 
          style={buttonSecondaryStyle}
        >
          ← {t.backToHome}
        </button>
      </div>

      {/* Форма входа */}
      <div style={cardStyle}>
        <div style={headerStyle}>🔐 {t.title}</div>
        <div style={subtitleStyle}>{t.subtitle}</div>
        
        {err && <div style={errorStyle}>{err}</div>}
        
        <form onSubmit={(e) => { e.preventDefault(); onLoginClick(); }}>
          <div style={{ marginBottom: getSpacing('lg') }}>
            <label style={labelStyle}>
              {t.selectRole}
            </label>
            <select
              value={selectedRoleKey}
              onChange={(e) => onSelectRole(e.target.value)}
              style={{
                ...inputStyle,
                background: theme === 'light' ? 'white' : getColor('gray', 800)
              }}
              disabled={busy}
            >
              {roleOptions.map((opt) => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: getSpacing('lg') }}>
            <label style={labelStyle}>
              {t.username}
            </label>
            <input 
              value={username} 
              onChange={(e) => setUsername(e.target.value)} 
              style={{
                ...inputStyle,
                opacity: 0.7,
                cursor: 'not-allowed'
              }}
              autoComplete="username" 
              disabled 
              readOnly 
            />
          </div>

          <div style={{ marginBottom: getSpacing('lg') }}>
            <label style={labelStyle}>
              {t.password}
            </label>
            <input 
              type="password" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              style={inputStyle}
              autoComplete="current-password" 
              disabled={busy}
              placeholder="••••••••"
            />
          </div>

          <div style={{ marginBottom: getSpacing('lg') }}>
            <button 
              type="submit" 
              disabled={busy} 
              style={{
                ...buttonStyle,
                opacity: busy ? 0.7 : 1,
                cursor: busy ? 'not-allowed' : 'pointer'
              }}
              onMouseOver={(e) => !busy && (e.target.style.transform = 'translateY(-2px)')}
              onMouseOut={(e) => !busy && (e.target.style.transform = 'translateY(0)')}
            >
              {busy ? t.loggingIn : t.login}
            </button>
          </div>

          <div style={{ textAlign: 'center', marginBottom: getSpacing('md') }}>
            <a 
              href="#" 
              style={{ 
                color: getColor('primary', 600), 
                textDecoration: 'none',
                fontSize: '14px'
              }}
              onClick={(e) => { e.preventDefault(); /* TODO: implement */ }}
            >
              {t.forgotPassword}
            </a>
          </div>
        </form>

        <div style={{ 
          fontSize: '12px', 
          opacity: 0.7, 
          lineHeight: '1.4', 
          textAlign: 'center',
          padding: getSpacing('sm'),
          background: theme === 'light' ? getColor('gray', 50) : getColor('gray', 800),
          borderRadius: '8px',
          border: `1px solid ${theme === 'light' ? getColor('gray', 200) : getColor('gray', 700)}`
        }}>
          💡 {t.note}
        </div>
      </div>
    </div>
  );
}



