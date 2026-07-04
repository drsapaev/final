import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowRight, AtSign, Eye, EyeOff, LogIn, CircleHelp, Phone, UserPlus, UserRound, AlertTriangle } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { api, setToken } from '../../api/client';
import { setProfile } from '../../stores/auth';
import { getRouteForProfile } from '../../constants/routes';
import { getCanonicalRouteById, getEffectiveRouteByPath } from '../../routing/routeSelectors.js';
import { useSetupStatus } from '../../hooks/useSetupStatus.js';
import { useTranslation } from '../../hooks/useTranslation.jsx';
import { colors } from '../../theme/tokens';
import { BRAND } from '../../config/brand';
import TwoFactorVerify from '../TwoFactorVerify.jsx';
import ForgotPassword from './ForgotPassword';
import { formatLoginErrorMessage, LOGIN_ERROR_MESSAGES } from './loginErrorUtils';
import {
  Button, Card, CardHeader, CardTitle, CardContent, Input, Select, Checkbox, Alert,
} from '../ui/macos';
import logger from '../../utils/logger';

const landingRoute = getCanonicalRouteById('landing')?.path || '/';
const loginRoute = getCanonicalRouteById('login')?.path || '/login';
const changePasswordRequiredRoute = getCanonicalRouteById('change-password-required')?.path || '/change-password-required';
const setupRoute = getCanonicalRouteById('setup')?.path || '/setup';

// UX Audit Stage 1 (Login issue 3.6):
// Удалён мёртвый floatingAnimation + вставка <style> в document.head.
// Анимация `float` нигде не использовалась — был только побочный эффект
// утечки стилей в глобальный DOM.

// UX Audit Stage 1 (Login issue 3.6):
// `void useTheme();` заменён на нормальный вызов — мы подписываемся
// на смену темы, чтобы карточка логина перерисовывалась.
const LoginFormStyled = () => {
  useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const setupStatus = useSetupStatus();
  // UX Audit Stage 2 (Login issue 3.5): передаём language в ForgotPassword.
  // Раньше ForgotPassword всегда использовал 'RU' по умолчанию, даже если
  // остальной UI на EN/UZ/KK. Теперь язык пробрасывается из useTranslation.
  const { language: rawLanguage } = useTranslation();
  // ForgotPassword ожидает 'RU'/'UZ'/'EN' (upper-case), useTranslation даёт 'ru'/'uz'/'en'.
  const language = (rawLanguage || 'ru').toUpperCase();
  const from = location.state?.from?.pathname || landingRoute;
  const showSetupCta = setupStatus.initialized === false;
  // UX Audit Stage 2 (Login issue 3.2): Caps Lock warning.
  // Detect через keyboard event (getModifierState('CapsLock')).
  const [capsLockOn, setCapsLockOn] = useState(false);
  const authControlStyles = {
    backgroundColor: 'rgba(255, 255, 255, 0.98)',
    color: '#0f172a',
    WebkitTextFillColor: '#0f172a',
    caretColor: '#0f172a',
    borderColor: 'rgba(148, 163, 184, 0.62)',
    boxShadow: '0 8px 20px rgba(15, 23, 42, 0.05)',
  };
  const authButtonBaseStyles = {
    borderRadius: '10px',
    fontWeight: '600',
    letterSpacing: '0.01em',
    boxShadow: 'none',
    WebkitBackdropFilter: 'none',
    backdropFilter: 'none',
  };
  const authSecondaryButtonStyles = {
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    color: '#0f172a',
    borderColor: 'rgba(148, 163, 184, 0.85)',
  };
  const authGhostButtonStyles = {
    backgroundColor: 'rgba(255, 255, 255, 0.88)',
    color: '#0f172a',
    borderColor: 'rgba(148, 163, 184, 0.58)',
    boxShadow: '0 6px 14px rgba(15, 23, 42, 0.06)',
  };
  const authPrimaryButtonStyles = {
    background: 'linear-gradient(135deg, #0a84ff 0%, #007aff 55%, #0060df 100%)',
    borderColor: '#007aff',
    color: 'white',
    boxShadow: '0 12px 24px rgba(0, 122, 255, 0.28)',
  };

  const [formData, setFormData] = useState({
    username: '',
    password: '',
    loginType: 'username'
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);

  // 2FA состояние
  const [requires2FA, setRequires2FA] = useState(false);
  const [pending2FAToken, setPending2FAToken] = useState('');
  const [twoFactorMethod, setTwoFactorMethod] = useState('totp');

  // Функция для проверки защищенных панелей
  const isProtectedPanelPath = (pathname) => {
    const route = getEffectiveRouteByPath(pathname);
    return Boolean(route && (route.group === 'clinical' || route.group === 'admin'));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Валидация обязательных полей
      if (!formData.username || !formData.password) {
        setError('Пожалуйста, введите логин и пароль');
        setLoading(false);
        return;
      }

      const credentials = {
        username: formData.username,
        password: formData.password,
        remember_me: rememberMe
      };

      logger.log('[AUTH] Login submit', {
        loginType: formData.loginType,
        rememberMe,
      });

      // UX Audit Stage 1 (Login issue 3.1.3 + 3.7):
      // Заменён raw fetch() на api.post() из api/client.
      // axios-клиент сам добавит Authorization-хедер на следующие запросы,
      // обрабатывает CSRF, refresh-token и rate-limit — всё в одном месте.
      let data;
      try {
        const response = await api.post('/authentication/login', credentials);
        data = response.data;
      } catch (apiErr) {
        // Нормализуем ошибку axios и пробрасываем дальше.
        const normalizedError = new Error(formatLoginErrorMessage({
          responseStatus: apiErr?.response?.status,
          responseDetail: apiErr?.response?.data?.detail,
          responseMessage: apiErr?.response?.data?.message,
          rawMessage: apiErr?.message,
          fallbackMessage: 'Ошибка авторизации',
        }));
        normalizedError.response = apiErr?.response;
        normalizedError.rawMessage = apiErr?.message;
        throw normalizedError;
      }

      // Проверяем, требуется ли 2FA (в простом сервере 2FA отключено)
      if (data.requires_2fa && data.pending_2fa_token) {
        setRequires2FA(true);
        setPending2FAToken(data.pending_2fa_token);
        setTwoFactorMethod(data.two_factor_method || 'totp');
        setLoading(false);
        return;
      }

      // Обычный вход без 2FA
      if (data.access_token) {
        const accessToken = typeof data.access_token === 'string' ? data.access_token.trim() : data.access_token;
        // Проверяем, требуется ли смена пароля
        if (data.must_change_password) {
          // UX Audit Stage 1: setToken() уже пишет в localStorage через tokenManager
          setToken(accessToken);
          navigate(changePasswordRequiredRoute, {
            state: { currentPassword: formData.password },
            replace: true
          });
          return;
        }

        // Сохраняем токен единообразно для всех клиентов
        // UX Audit Stage 1 (issue 3.1.3): удалён дублирующий localStorage.setItem
        setToken(accessToken);

        try {
          // UX Audit Stage 1 (Login issue 3.7):
          // Удалён 100-мс setTimeout + auth.getState() race-condition workaround.
          // Теперь используем data.user напрямую из ответа сервера.
          setProfile(data.user);
          const profile = data.user || null;
          const computedRoute = getRouteForProfile(profile);
          const fromClean = from || landingRoute;

          // Если from ведёт на другой защищённый раздел панели — игнорируем его
          let target = computedRoute;
          if (fromClean && fromClean !== landingRoute && fromClean !== loginRoute) {
            if (isProtectedPanelPath(fromClean)) {
              if (fromClean === computedRoute) target = fromClean;
            } else {
              // Нефреймовый/просмотровый маршрут (детали визита и т.п.) — разрешаем возврат
              target = fromClean;
            }
          }

          // Детальная аналитика входа
          logger.log('🔐 Login redirect:', {
            from: fromClean,
            computedRoute,
            target,
            profile: profile?.role || 'unknown',
            timestamp: new Date().toISOString()
          });

          navigate(target, { replace: true });
        } catch (profileError) {
          logger.warn('Не удалось получить профиль:', profileError);
          navigate(landingRoute, { replace: true });
        }
      } else {
        throw new Error('Не получен токен доступа');
      }
    } catch (err) {
      // Улучшенная обработка ошибок с нормализацией
      const rawMessage = typeof err?.message === 'string' ? err.message : '';
      const errorMessage = formatLoginErrorMessage({
        responseStatus: err?.response?.status,
        responseDetail: err?.response?.data?.detail,
        responseMessage: err?.response?.data?.message,
        rawMessage: err?.normalizedMessage || rawMessage,
        fallbackMessage: 'Ошибка входа',
      });

      if (rawMessage && /failed to fetch/i.test(rawMessage)) {
        logger.warn('[FIX:LOGIN] Network login failure normalized', {
          loginType: formData.loginType,
          hasIdentifier: Boolean(formData.username),
          rawMessage,
          normalizedMessage: LOGIN_ERROR_MESSAGES.NETWORK,
          timestamp: new Date().toISOString(),
        });
      }

      // Логирование ошибки для аналитики
      logger.error('🚨 Login error:', {
        error: errorMessage,
        rawMessage,
        timestamp: new Date().toISOString(),
        loginType: formData.loginType,
        hasIdentifier: Boolean(formData.username)
      });

      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handle2FASuccess = async (response) => {
    try {
      if (response.data?.access_token) {
        const accessToken = typeof response.data.access_token === 'string' ? response.data.access_token.trim() : response.data.access_token;
        setToken(accessToken);

        const profileResponse = await api.get('/auth/me');
        setProfile(profileResponse.data);

        // UX Audit Stage 1 (Login issue 3.7):
        // Удалён 100-мс setTimeout + auth.getState() — используем profileResponse.data.
        const profile = profileResponse.data || null;
        const computedRoute = getRouteForProfile(profile);
        const target = computedRoute || from || landingRoute;

        navigate(target, { replace: true });
      }
    } catch {
      setError('Ошибка после 2FA верификации');
      setRequires2FA(false);
    }
  };

  const handle2FACancel = () => {
    setRequires2FA(false);
    setPending2FAToken('');
    setError('');
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value
    }));
  };

  // UX Audit Stage 2 (Login issue 3.2): обработчики Caps Lock detection.
  // getModifierState('CapsLock') работает в keydown/keyup/keypress.
  // На keyup сбрасываем, на keydown — обновляем.
  const handleKeyDown = (e) => {
    if (typeof e.getModifierState === 'function') {
      setCapsLockOn(e.getModifierState('CapsLock'));
    }
  };

  const handleKeyUp = (e) => {
    if (typeof e.getModifierState === 'function') {
      setCapsLockOn(e.getModifierState('CapsLock'));
    }
  };

  // UX Audit Stage 2 (Login issue 3.4): 2FA-табы через proper ARIA roles.
  // Раньше это были 3 обычные <button> без role/aria-selected/aria-controls.
  // Теперь это proper tablist с keyboard navigation support.
  const twoFactorTabs = [
    { id: 'totp', label: 'Приложение' },
    { id: 'backup', label: 'Backup код' },
    { id: 'recovery', label: 'Восстановление' },
  ];
  const twoFactorTabPanelId = 'twofactor-tabpanel';

  const handle2FATabKeyDown = (e, index) => {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      const next = twoFactorTabs[(index + 1) % twoFactorTabs.length];
      setTwoFactorMethod(next.id);
      document.getElementById(`twofactor-tab-${next.id}`)?.focus();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      const prev = twoFactorTabs[(index - 1 + twoFactorTabs.length) % twoFactorTabs.length];
      setTwoFactorMethod(prev.id);
      document.getElementById(`twofactor-tab-${prev.id}`)?.focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      const first = twoFactorTabs[0];
      setTwoFactorMethod(first.id);
      document.getElementById(`twofactor-tab-${first.id}`)?.focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      const last = twoFactorTabs[twoFactorTabs.length - 1];
      setTwoFactorMethod(last.id);
      document.getElementById(`twofactor-tab-${last.id}`)?.focus();
    }
  };

  // Если требуется 2FA, показываем компонент верификации
  if (requires2FA) {
    return (
      <div style={{
        minHeight: '100vh',
        background: `linear-gradient(135deg, ${colors.primary[500]} 0%, ${colors.primary[700]} 100%)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px'
      }}>
        <div style={{
          background: 'white',
          borderRadius: '12px',
          boxShadow: '0 20px 40px rgba(0,0,0,0.1)',
          padding: '40px',
          width: '100%',
          maxWidth: '400px',
          position: 'relative'
        }}>
          <div style={{
            textAlign: 'center',
            marginBottom: '30px'
          }}>
            <div style={{
              width: '60px',
              height: '60px',
              background: `linear-gradient(135deg, ${colors.primary[500]} 0%, ${colors.primary[700]} 100%)`,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
              fontSize: '24px',
              color: 'white',
              position: 'relative'
            }}>
              <div style={{
                position: 'absolute',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.2)',
                borderRadius: '50%'
              }} />
              <span style={{ position: 'relative', zIndex: 1 }}>🔐</span>
            </div>
            <h1 style={{
              fontSize: '24px',
              fontWeight: 'bold',
              color: colors.semantic.text.primary,
              margin: '0 0 8px 0'
            }}>
              Двухфакторная аутентификация
            </h1>
            <p style={{
              color: colors.semantic.text.secondary,
              margin: '0',
              fontSize: '14px'
            }}>
              Подтвердите вход с помощью кода
            </p>
          </div>

          {/* UX Audit Stage 2 (Login issue 3.4):
              Переключатель методов 2FA теперь proper tablist с ARIA roles.
              Раньше это были 3 обычные <button> без role/aria-selected/aria-controls.
              Теперь screen reader правильно объявляет это как таб-лист с 3 табами.
              Keyboard navigation: ArrowLeft/Right, Home, End. */}
          <div style={{ marginBottom: '20px' }}>
            <div
              role="tablist"
              aria-label="Методы двухфакторной аутентификации"
              style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}
            >
              {twoFactorTabs.map((tab, index) => {
                const isActive = twoFactorMethod === tab.id;
                return (
                  <button
                    key={tab.id}
                    id={`twofactor-tab-${tab.id}`}
                    role="tab"
                    type="button"
                    aria-selected={isActive}
                    aria-controls={twoFactorTabPanelId}
                    tabIndex={isActive ? 0 : -1}
                    onClick={() => setTwoFactorMethod(tab.id)}
                    onKeyDown={(e) => handle2FATabKeyDown(e, index)}
                    style={{
                      flex: 1,
                      padding: '8px 12px',
                      background: isActive ? colors.primary[500] : 'transparent',
                      color: isActive ? 'white' : colors.semantic.text.secondary,
                      border: '1px solid #e1e5e9',
                      borderRadius: '6px',
                      fontSize: '12px',
                      cursor: 'pointer',
                      font: 'inherit',
                      outline: isActive ? `2px solid ${colors.primary[500]}` : 'none',
                      outlineOffset: '2px',
                    }}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div
            id={twoFactorTabPanelId}
            role="tabpanel"
            aria-labelledby={`twofactor-tab-${twoFactorMethod}`}
            tabIndex={-1}
          >
            <TwoFactorVerify
              method={twoFactorMethod}
              pendingToken={pending2FAToken}
              onSuccess={handle2FASuccess}
              onCancel={handle2FACancel} />
          </div>

        </div>
      </div>);

  }

  // Если нажали "Забыли пароль", показываем компонент восстановления
  if (showForgotPassword) {
    return (
      <div
        className="login-forgot-wrap"
        style={{
          minHeight: '100vh',
          // UX Audit Stage 2 (Login issue 3.3): используем --mac-bg-primary
          // вместо хардкода #1d1d1f. Теперь фон следует за темой приложения.
          background: 'var(--mac-bg-primary, #1d1d1f)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
          position: 'relative'
        }}
      >
        {/* UX Audit Stage 2 (Login issue 3.5): передаём language в ForgotPassword.
            Раньше ForgotPassword всегда использовал 'RU' по умолчанию. */}
        <ForgotPassword
          language={language}
          onBack={() => setShowForgotPassword(false)}
          onSuccess={() => setShowForgotPassword(false)} />

      </div>);

  }

  return (
    <div
      className="login-auth-wrap"
      style={{
        minHeight: '100vh',
        // UX Audit Stage 2 (Login issue 3.3): заменён хардкод #1d1d1f на --mac-bg-primary.
        // Раньше login был всегда тёмный, независимо от темы приложения.
        // Теперь фон следует за light/dark темой.
        background: 'var(--mac-bg-primary, #1d1d1f)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        position: 'relative'
      }}
    >

      <Card className="login-form-auth" style={{
        width: '100%',
      maxWidth: '400px',
      // macOS-стиль карточки: полупрозрачная с размытием
      background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.84) 0%, rgba(248, 250, 252, 0.74) 100%)',
        backdropFilter: 'blur(26px) saturate(140%)',
        WebkitBackdropFilter: 'blur(26px) saturate(140%)',
        border: '1px solid rgba(255, 255, 255, 0.42)',
        boxShadow: `
          0 18px 48px rgba(15, 23, 42, 0.18),
          0 2px 8px rgba(15, 23, 42, 0.06),
          inset 0 1px 0 rgba(255, 255, 255, 0.55)
        `,
        borderRadius: '24px',
        overflow: 'hidden',
        position: 'relative',
        zIndex: 1
      }}>
        <CardHeader>
          <CardTitle style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
            textAlign: 'center'
          }}>
            <span style={{
              fontSize: '24px',
              fontWeight: '600',
              // UX Audit Stage 2 (Login issue 3.3): --mac-text-primary вместо #1d1d1f
              color: 'var(--mac-text-primary, #1d1d1f)',
              letterSpacing: '-0.5px'
            }}>
              {/* UX Audit Stage 2 (Login issue 3.5): aria-hidden на эмодзи,
                  чтобы скринридер не читал «encryption key emoji». */}
              <span aria-hidden="true">🔐</span>{' '}Вход в систему
            </span>
            <span style={{
              fontSize: '14px',
              fontWeight: '400',
              // UX Audit Stage 2 (Login issue 3.3): --mac-text-secondary вместо #86868b
              color: 'var(--mac-text-secondary, #86868b)',
              letterSpacing: '0.1px'
            }}>
              {/* UX Audit Stage 1: используем единый BRAND config вместо хардкода */}
              {BRAND.name}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent style={{ paddingTop: 12, paddingBottom: 14 }}>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--mac-text-primary, #1d1d1f)', fontWeight: 500 }}>Тип входа</label>
              <Select
                value={formData.loginType}
                onChange={(val) => setFormData((prev) => ({ ...prev, loginType: val }))}
                options={[
                { value: 'username', label: <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><UserRound size={14} />Имя пользователя</span> },
                { value: 'email', label: <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><AtSign size={14} />Email</span> },
                { value: 'phone', label: <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><Phone size={14} />Телефон</span> }]
                } />

            </div>

            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--mac-text-primary, #1d1d1f)', fontWeight: 500 }}>
                {formData.loginType === 'username' ? 'Имя пользователя' : formData.loginType === 'email' ? 'Email' : 'Телефон'} *
              </label>
              <Input
                type={formData.loginType === 'email' ? 'email' : 'text'}
                name="username"
                value={formData.username}
                onChange={handleInputChange}
                required
                autoComplete={formData.loginType === 'email' ? 'email' : 'username'}
                placeholder={`Введите ${formData.loginType === 'username' ? 'имя пользователя' : formData.loginType === 'email' ? 'email' : 'телефон'}`}
                style={authControlStyles} />

            </div>

            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--mac-text-primary, #1d1d1f)', fontWeight: 500 }}>Пароль *</label>
              <div style={{ position: 'relative' }}>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  // UX Audit Stage 2 (Login issue 3.2): Caps Lock detection.
                  onKeyDown={handleKeyDown}
                  onKeyUp={handleKeyUp}
                  required
                  autoComplete="current-password"
                  placeholder="Введите пароль"
                  style={authControlStyles}
                  aria-describedby={capsLockOn ? 'capslock-warning' : undefined}
                />

                <Button type="button" variant="ghost" size="small" onClick={() => setShowPassword(!showPassword)} style={{ position: 'absolute', right: 4, top: 4, ...authGhostButtonStyles, ...authButtonBaseStyles }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                    {showPassword ? 'Скрыть' : 'Показать'}
                  </span>
                </Button>
              </div>

              {/* UX Audit Stage 2 (Login issue 3.2): Caps Lock warning. */}
              {capsLockOn && (
                <div
                  id="capslock-warning"
                  role="alert"
                  aria-live="polite"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    marginTop: 6,
                    padding: '6px 10px',
                    fontSize: 12,
                    fontWeight: 600,
                    color: '#b45309',
                    background: 'rgba(245, 158, 11, 0.12)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    borderRadius: 8,
                  }}
                >
                  <AlertTriangle size={14} aria-hidden="true" />
                  <span>Caps Lock включён — проверьте регистр пароля</span>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', gap: 8 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Checkbox checked={rememberMe} onChange={(checked) => setRememberMe(checked)} /> Запомнить меня
              </label>
              <Button type="button" variant="ghost" size="small" onClick={() => setShowForgotPassword(true)} style={{ ...authGhostButtonStyles, ...authButtonBaseStyles }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <CircleHelp size={14} />
                  Забыли пароль?
                </span>
              </Button>
            </div>

            {error &&
            <Alert variant="danger" style={{ marginBottom: 12 }}>{error}</Alert>
            }

            {/* UX Audit Stage 1 (Login issue 3.1.2):
                Раньше было type='button' + onClick={handleSubmit} — двойной путь сабмита
                с формой. Теперь type='submit' — единственный путь, форма сама вызовет
                handleSubmit через onSubmit. */}
            <Button type="submit" variant="primary" fullWidth disabled={loading} size="large" style={{ ...authPrimaryButtonStyles, ...authButtonBaseStyles }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <LogIn size={16} />
                {loading ? 'Вход...' : 'ВОЙТИ'}
                {!loading && <ArrowRight size={16} />}
              </span>
            </Button>
          </form>

          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            {showSetupCta && (
            <Button type="button" variant="outline" fullWidth size="small" onClick={() => navigate(setupRoute)} style={{ ...authSecondaryButtonStyles, ...authButtonBaseStyles }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <UserPlus size={16} />
                Создать клинику
              </span>
            </Button>
            )}
            <Button type="button" variant="outline" fullWidth size="small" onClick={() => navigate(landingRoute)} style={{ ...authSecondaryButtonStyles, ...authButtonBaseStyles }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <UserRound size={16} />
                {/* UX Audit Stage 2 (Login issue 3.2): «Гость» вводил в заблуждение —
                    это не гостевой режим, а просто возврат на лендинг. */}
                На главную
              </span>
            </Button>
          </div>
        </CardContent>
        {/*
          UX Audit Stage 2 (Login issue 3.3):
          Стили перенесены с хардкодов (#0f172a, #64748b) на design tokens.
          Теперь поля ввода на login-экране корректно работают в light/dark теме.
          Раньше login был всегда тёмный, и эти стили форсировали тёмный текст —
          в light-теме приложения это выглядело инородно.
        */}
        <style>{`
          .login-form-auth .mac-input,
          .login-form-auth .mac-input-label,
          .login-form-auth .mac-input-hint,
          .login-form-auth .mac-input-error {
            color: var(--mac-text-primary, #0f172a) !important;
          }

          .login-form-auth .mac-input::placeholder {
            color: var(--mac-text-secondary, #64748b) !important;
            opacity: 1 !important;
          }

          .login-form-auth .mac-select-trigger {
            background: color-mix(in srgb, var(--mac-card-bg, #ffffff) 96%, transparent) !important;
            color: var(--mac-text-primary, #0f172a) !important;
            border-color: color-mix(in srgb, var(--mac-card-border, #cbd5e1) 70%, transparent) !important;
          }

          .login-form-auth .mac-select-trigger span,
          .login-form-auth .mac-select-trigger svg {
            color: inherit !important;
          }

          .login-form-auth .mac-select-list {
            background: color-mix(in srgb, var(--mac-card-bg, #ffffff) 98%, transparent) !important;
            color: var(--mac-text-primary, #0f172a) !important;
            border-color: color-mix(in srgb, var(--mac-card-border, #cbd5e1) 70%, transparent) !important;
          }

          .login-form-auth .mac-select-item {
            color: var(--mac-text-primary, #0f172a) !important;
          }

          .login-form-auth .mac-select-item:hover {
            color: var(--mac-text-primary, #0f172a) !important;
            background: color-mix(in srgb, var(--mac-accent-blue, #2563eb) 8%, transparent) !important;
          }

          .login-form-auth .mac-button {
            transition: transform 0.16s ease, box-shadow 0.16s ease, background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
          }

          .login-form-auth .mac-button span {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
          }

          .login-form-auth .mac-button:hover {
            box-shadow: 0 10px 18px color-mix(in srgb, var(--mac-text-primary, #0f172a) 8%, transparent) !important;
            transform: translateY(-1px);
          }

          .login-form-auth .mac-button:active {
            transform: translateY(0) scale(0.99);
          }

          .login-form-auth .mac-button[disabled] {
            opacity: 0.7 !important;
            cursor: not-allowed !important;
          }
        `}</style>
      </Card>
    </div>);

};

export default LoginFormStyled;
