import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { login, me, setToken } from '../api/client';
import { setProfile } from '../stores/auth';
import auth from '../stores/auth.js';
import { ROLE_OPTIONS, getRouteForProfile } from '../constants/routes';
import ForgotPassword from '../components/auth/ForgotPassword';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSInput, 
  MacOSSelect,
  MacOSBadge
} from '../components/ui/macos';
import { 
  Lock, 
  User, 
  Key, 
  ArrowLeft, 
  Sun, 
  Moon,
  Globe,
  Eye,
  EyeOff
} from 'lucide-react';

/**
 * Логин по OAuth2 Password (FastAPI):
 * POST /login с application/x-www-form-urlencoded полями:
 *   username, password, grant_type=password, scope, client_id, client_secret
 */
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
  const [theme, setTheme] = useState('light');

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

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  function onSelectRole(k) {
    setSelectedRoleKey(k);
    const found = roleOptions.find(r => r.key === k);
    if (found) setUsername(found.username);
  }

  async function performLogin(u, p) {
    try {
      // Используем централизованный API клиент
      const data = await login(u, p);
      const token = data?.access_token;
      if (!token) throw new Error('В ответе не найден access_token');
      
      // Устанавливаем токен (interceptor автоматически добавит его в заголовки)
      setToken(token);
      
      try {
        // Получаем профиль пользователя
        const profile = await me();
        setProfile(profile);
      } catch (profileError) {
        console.warn('Не удалось получить профиль:', profileError);
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
      
      const state = auth.getState ? auth.getState() : { profile: null };
      return getRouteForProfile(state?.profile) || defaultPath;
    } catch (error) {
      console.error('pickRouteForRoleCached error:', error);
      return defaultPath;
    }
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
      const computedRoute = getRouteForProfile(profile);
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
      // Используем нормализованное сообщение об ошибке
      const errorMessage = e2?.normalizedMessage || e2?.message || 'Ошибка входа';
      setErr(errorMessage);
    } finally {
      setBusy(false);
    }
  }

  const pageStyle = {
    minHeight: '100vh',
    background: theme === 'light' 
      ? 'linear-gradient(135deg, var(--mac-bg-primary) 0%, var(--mac-bg-secondary) 100%)'
      : 'linear-gradient(135deg, var(--mac-bg-primary) 0%, var(--mac-bg-secondary) 100%)',
    padding: 'var(--mac-spacing-lg)',
    fontFamily: 'var(--mac-font-family)',
    color: 'var(--mac-text-primary)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center'
  };

  const headerStyle = {
    fontSize: 'var(--mac-font-size-2xl)',
    fontWeight: 'var(--mac-font-weight-bold)',
    marginBottom: 'var(--mac-spacing-sm)',
    color: 'var(--mac-text-primary)',
    textAlign: 'center',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 'var(--mac-spacing-sm)'
  };

  const subtitleStyle = {
    fontSize: 'var(--mac-font-size-base)',
    color: 'var(--mac-text-secondary)',
    marginBottom: 'var(--mac-spacing-xl)',
    textAlign: 'center',
    lineHeight: '1.5'
  };

  const errorStyle = {
    color: 'var(--mac-error)',
    background: 'var(--mac-error-bg)',
    border: '1px solid var(--mac-error-border)',
    borderRadius: 'var(--mac-radius-sm)',
    padding: 'var(--mac-spacing-sm)',
    marginBottom: 'var(--mac-spacing-md)',
    fontSize: 'var(--mac-font-size-sm)'
  };

  const toggleButtonStyle = {
    padding: 'var(--mac-spacing-xs)',
    background: 'var(--mac-bg-secondary)',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-sm)',
    cursor: 'pointer',
    color: 'var(--mac-text-primary)',
    marginLeft: 'var(--mac-spacing-sm)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px',
    transition: 'all 0.2s ease'
  };

  // Если показываем форму восстановления пароля
  if (showForgotPassword) {
    return (
      <div style={pageStyle}>
        {/* Переключатели темы и языка */}
        <div style={{ 
          position: 'absolute', 
          top: 'var(--mac-spacing-lg)', 
          right: 'var(--mac-spacing-lg)', 
          display: 'flex', 
          alignItems: 'center',
          gap: 'var(--mac-spacing-sm)'
        }}>
          <button 
            onClick={() => toggleTheme()}
            style={toggleButtonStyle}
            title="Переключить тему"
          >
            {theme === 'light' ? <Moon style={{ width: '16px', height: '16px' }} /> : <Sun style={{ width: '16px', height: '16px' }} />}
          </button>
          <MacOSSelect
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={{
              ...toggleButtonStyle,
              width: '60px',
              height: '32px',
              padding: '0 var(--mac-spacing-xs)'
            }}
          >
            <option value="RU">RU</option>
            <option value="UZ">UZ</option>
            <option value="EN">EN</option>
          </MacOSSelect>
        </div>

        <ForgotPassword
          language={language}
          onBack={() => setShowForgotPassword(false)}
          onSuccess={() => {
            setShowForgotPassword(false);
            setErr('');
          }}
        />
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      {/* Переключатели темы и языка */}
      <div style={{ 
        position: 'absolute', 
        top: 'var(--mac-spacing-lg)', 
        right: 'var(--mac-spacing-lg)', 
        display: 'flex', 
        alignItems: 'center',
        gap: 'var(--mac-spacing-sm)'
      }}>
        <button 
          onClick={() => toggleTheme()}
          style={toggleButtonStyle}
          title="Переключить тему"
        >
          {theme === 'light' ? <Moon style={{ width: '16px', height: '16px' }} /> : <Sun style={{ width: '16px', height: '16px' }} />}
        </button>
        <MacOSSelect
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          style={{
            ...toggleButtonStyle,
            width: '60px',
            height: '32px',
            padding: '0 var(--mac-spacing-xs)'
          }}
        >
          <option value="RU">RU</option>
          <option value="UZ">UZ</option>
          <option value="EN">EN</option>
        </MacOSSelect>
      </div>

      {/* Кнопка "На главную" */}
      <div style={{ position: 'absolute', top: 'var(--mac-spacing-lg)', left: 'var(--mac-spacing-lg)' }}>
        <MacOSButton 
          onClick={() => navigate('/')} 
          variant="outline"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 'var(--mac-spacing-xs)',
            fontSize: 'var(--mac-font-size-sm)'
          }}
        >
          <ArrowLeft style={{ width: '16px', height: '16px' }} />
          {t.backToHome}
        </MacOSButton>
      </div>

      {/* Форма входа */}
      <MacOSCard style={{ 
        maxWidth: '450px',
        width: '100%',
        padding: 'var(--mac-spacing-2xl)',
        backdropFilter: 'blur(20px)',
        background: 'var(--mac-bg-glass)',
        border: '1px solid var(--mac-border-glass)'
      }}>
        <div style={headerStyle}>
          <Lock style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
          {t.title}
        </div>
        <div style={subtitleStyle}>{t.subtitle}</div>
        
        {err && <div style={errorStyle}>{err}</div>}
        
        <form onSubmit={(e) => { e.preventDefault(); onLoginClick(); }}>
          <div style={{ marginBottom: 'var(--mac-spacing-lg)' }}>
            <label style={{ 
              display: 'block',
              marginBottom: 'var(--mac-spacing-xs)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              {t.selectRole}
            </label>
            <MacOSSelect
              value={selectedRoleKey}
              onChange={(e) => onSelectRole(e.target.value)}
              disabled={busy}
              style={{ width: '100%' }}
            >
              {roleOptions.map((opt) => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </MacOSSelect>
          </div>

          <div style={{ marginBottom: 'var(--mac-spacing-lg)' }}>
            <label style={{ 
              display: 'block',
              marginBottom: 'var(--mac-spacing-xs)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              {t.username}
            </label>
            <MacOSInput 
              value={username} 
              onChange={(e) => setUsername(e.target.value)} 
              autoComplete="username" 
              disabled 
              readOnly 
              style={{ 
                opacity: 0.7,
                cursor: 'not-allowed',
                width: '100%'
              }}
            />
          </div>

          <div style={{ marginBottom: 'var(--mac-spacing-lg)' }}>
            <label style={{ 
              display: 'block',
              marginBottom: 'var(--mac-spacing-xs)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              {t.password}
            </label>
            <div style={{ position: 'relative' }}>
              <MacOSInput 
                type={showPassword ? "text" : "password"}
                value={password} 
                onChange={(e) => setPassword(e.target.value)} 
                autoComplete="current-password" 
                disabled={busy}
                placeholder="••••••••"
                style={{ width: '100%', paddingRight: '40px' }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: 'var(--mac-spacing-sm)',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--mac-text-secondary)',
                  padding: 'var(--mac-spacing-xs)',
                  borderRadius: 'var(--mac-radius-sm)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                {showPassword ? <EyeOff style={{ width: '16px', height: '16px' }} /> : <Eye style={{ width: '16px', height: '16px' }} />}
              </button>
            </div>
          </div>

          <div style={{ marginBottom: 'var(--mac-spacing-lg)' }}>
            <MacOSButton 
              type="submit" 
              disabled={busy} 
              variant="primary"
              style={{ width: '100%' }}
            >
              {busy ? t.loggingIn : t.login}
            </MacOSButton>
          </div>

          <div style={{ textAlign: 'center', marginBottom: 'var(--mac-spacing-md)' }}>
            <MacOSButton 
              variant="ghost"
              onClick={(e) => { e.preventDefault(); setShowForgotPassword(true); }}
              style={{ 
                color: 'var(--mac-accent-blue)', 
                fontSize: 'var(--mac-font-size-sm)',
                padding: '0'
              }}
            >
              {t.forgotPassword}
            </MacOSButton>
          </div>
        </form>

        <MacOSCard style={{ 
          fontSize: 'var(--mac-font-size-xs)', 
          color: 'var(--mac-text-tertiary)', 
          lineHeight: '1.4', 
          textAlign: 'center',
          padding: 'var(--mac-spacing-sm)',
          background: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          marginTop: 'var(--mac-spacing-md)'
        }}>
          💡 {t.note}
        </MacOSCard>
      </MacOSCard>
    </div>
  );
}



