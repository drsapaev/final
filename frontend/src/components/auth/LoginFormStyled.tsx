import { useState } from 'react';
import type { CSSProperties } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, LogIn, CircleHelp, UserPlus, UserRound, AlertTriangle } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { api, setToken, setRefreshToken } from '../../api/client';
import { setProfile } from '../../stores/auth';
import { getRouteForProfile } from '../../constants/routes';
import { getCanonicalRouteById, getEffectiveRouteByPath } from '../../routing/routeSelectors';
import { useSetupStatus } from '../../hooks/useSetupStatus';
import * as _tokens from '../../theme/tokens';
const colors = ((_tokens as Record<string, unknown>).colors || {}) as Record<string, unknown>;
import { BRAND } from '../../config/brand';
import TwoFactorVerify from '../TwoFactorVerify';
import ForgotPassword from './ForgotPassword';
import { formatLoginErrorMessage, LOGIN_ERROR_MESSAGES } from './loginErrorUtils';
import {
  Button, Card, CardHeader, CardTitle, CardContent, Input, Checkbox, Alert,
} from '../ui/macos';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // UX Audit: useTheme — используем isDark для conditional styles.
  const { isDark } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const setupStatus = useSetupStatus();
  const { language: rawLanguage } = useTranslation();
  const language = (rawLanguage || 'ru').toUpperCase();
  const from = location.state?.from?.pathname || landingRoute;
  const showSetupCta = setupStatus.initialized === false;
  const [capsLockOn, setCapsLockOn] = useState(false);

  // UX Audit: все стили используют --mac-* tokens, следуют за темой.
  const authControlStyles = {
    backgroundColor: isDark
      ? 'color-mix(in srgb, var(--mac-card-bg, #1c1c1e), transparent 2%)'
      : 'color-mix(in srgb, var(--mac-card-bg, #ffffff), transparent 2%)',
    color: 'var(--mac-text-primary, #0f172a)',
    WebkitTextFillColor: 'var(--mac-text-primary, #0f172a)',
    caretColor: 'var(--mac-text-primary, #0f172a)',
    borderColor: 'color-mix(in srgb, var(--mac-card-border, #cbd5e1), transparent 38%)',
    boxShadow: '0 4px 12px color-mix(in srgb, var(--mac-text-primary, #0f172a), transparent 92%)',
  };
  const authButtonBaseStyles = {
    borderRadius: 'var(--mac-radius-lg)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    letterSpacing: '0.01em',
    boxShadow: 'none',
    WebkitBackdropFilter: 'none',
    backdropFilter: 'none',
  };
  const authSecondaryButtonStyles = {
    backgroundColor: isDark
      ? 'color-mix(in srgb, var(--mac-card-bg, #1c1c1e), transparent 5%)'
      : 'color-mix(in srgb, var(--mac-card-bg, #ffffff), transparent 5%)',
    color: 'var(--mac-text-primary, #0f172a)',
    borderColor: 'color-mix(in srgb, var(--mac-card-border, #cbd5e1), transparent 15%)',
  };
  const authGhostButtonStyles = {
    backgroundColor: 'transparent',
    color: 'var(--mac-text-primary, #0f172a)',
    borderColor: 'transparent',
    boxShadow: 'none',
  };
  const authPrimaryButtonStyles = {
    background: 'linear-gradient(135deg, var(--mac-accent-blue, #0a84ff) 0%, var(--mac-accent-blue, #007aff) 55%, var(--mac-accent-blue, #0060df) 100%)',
    borderColor: 'var(--mac-accent-blue, #007aff)',
    color: 'var(--mac-text-on-accent, white)',
    boxShadow: '0 8px 20px color-mix(in srgb, var(--mac-accent-blue, #007aff), transparent 72%)',
  };

  const [formData, setFormData] = useState<{ username: string; password: string }>({
    username: '',
    password: '',
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
        setError(t('misc.lfs_pozhaluysta_vvedite_login_i_'));
        setLoading(false);
        return;
      }

      const credentials = {
        username: formData.username,
        password: formData.password,
        remember_me: rememberMe
      };

      logger.log('[AUTH] Login submit', {
        
        rememberMe,
      });

      // UX Audit Stage 1 (Login issue 3.1.3 + 3.7):
      // Заменён raw fetch() на api.post() из api/client.
      // axios-клиент сам добавит Authorization-хедер на следующие запросы,
      // обрабатывает CSRF, refresh-token и rate-limit — всё в одном месте.
      let data;
      try {
        const response = (await api.post('/authentication/login', credentials)) as import('axios').AxiosResponse<Record<string, unknown>>;
        data = response.data;
      } catch (apiErr: unknown) {
        // Нормализуем ошибку axios и пробрасываем дальше.
        const apiErrExtra = apiErr as { response?: { status?: number; data?: { detail?: string; message?: string } }; message?: string };
        const normalizedError = new Error(formatLoginErrorMessage({
          responseStatus: apiErrExtra?.response?.status,
          responseDetail: apiErrExtra?.response?.data?.detail,
          responseMessage: apiErrExtra?.response?.data?.message,
          rawMessage: apiErrExtra?.message,
          fallbackMessage: t('misc.lfs_oshibka_avtorizatsii'),
        })) as Error & { response?: unknown; rawMessage?: string };
        normalizedError.response = apiErrExtra?.response;
        normalizedError.rawMessage = apiErrExtra?.message;
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
          if (data.refresh_token) {
            setRefreshToken(data.refresh_token);
          }
          navigate(changePasswordRequiredRoute, {
            state: { currentPassword: formData.password },
            replace: true
          });
          return;
        }

        // Сохраняем токен единообразно для всех клиентов
        // UX Audit Stage 1 (issue 3.1.3): удалён дублирующий localStorage.setItem
        setToken(accessToken);
        // SECURITY/AUTH-REAUDIT-28: persist refresh_token — раньше не сохранялся,
        // из-за чего proactive-refresh в api/client.js был мёртвым кодом, и пользователь
        // молча разлогинивался каждые 30 минут.
        if (data.refresh_token) {
          setRefreshToken(data.refresh_token);
        }

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
        throw new Error(t('misc.lfs_ne_poluchen_token_dostupa'));
      }
    } catch (err) {
      // Улучшенная обработка ошибок с нормализацией
      const rawMessage = typeof err?.message === 'string' ? err.message : '';
      const errorMessage = formatLoginErrorMessage({
        responseStatus: err?.response?.status,
        responseDetail: err?.response?.data?.detail,
        responseMessage: err?.response?.data?.message,
        rawMessage: err?.normalizedMessage || rawMessage,
        fallbackMessage: t('misc.lfs_oshibka_vhoda'),
      });

      if (rawMessage && /failed to fetch/i.test(rawMessage)) {
        logger.warn('[FIX:LOGIN] Network login failure normalized', {
          
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
        // AUTH-REAUDIT-28: persist rotated refresh token after 2FA completion.
        if (response.data?.refresh_token) {
          setRefreshToken(response.data.refresh_token);
        }

        const profileResponse = (await api.get('/auth/me')) as import('axios').AxiosResponse<Record<string, unknown>>;
        setProfile(profileResponse.data);

        // UX Audit Stage 1 (Login issue 3.7):
        // Удалён 100-мс setTimeout + auth.getState() — используем profileResponse.data.
        const profile = profileResponse.data || null;
        const computedRoute = getRouteForProfile(profile);
        const target = computedRoute || from || landingRoute;

        navigate(target, { replace: true });
      }
    } catch {
      setError(t('misc.lfs_oshibka_posle_2fa_verifikats'));
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
    { id: 'totp', label: t('misc.lfs_prilozhenie') },
    { id: 'backup', label: t('misc.lfs_backup_kod') },
    { id: 'recovery', label: t('misc.lfs_vosstanovlenie') },
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
        background: `linear-gradient(135deg, ${colors.primary as string[500]} 0%, ${colors.primary as string[700]} 100%)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--mac-spacing-5)'
      }}>
        <div style={{
          background: 'white',
          borderRadius: 'var(--mac-radius-lg)',
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
              background: `linear-gradient(135deg, ${colors.primary as string[500]} 0%, ${colors.primary as string[700]} 100%)`,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
              fontSize: 'var(--mac-font-size-3xl)',
              color: 'white',
              position: 'relative'
            }}>
              <div style={{
                position: 'absolute',
                inset: 0,
                background: 'color-mix(in srgb, black, transparent 80%)',
                borderRadius: '50%'
              }} />
              <span style={{ position: 'relative', zIndex: 1 }}>🔐</span>
            </div>
            <h1 style={{
              fontSize: 'var(--mac-font-size-3xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: (colors.semantic as { text?: { primary?: string } })?.text?.primary,
              margin: '0 0 8px 0'
            }}>
              Двухфакторная аутентификация
            </h1>
            <p style={{
              color: (colors.semantic as { text?: { secondary?: string } })?.text?.secondary,
              margin: '0',
              fontSize: 'var(--mac-font-size-base)'
            }}>
              Подтвердите вход с помощью кода
            </p>
          </div>

          {/* UX Audit Stage 2 (Login issue 3.4):
              Переключатель методов 2FA теперь proper tablist с ARIA roles.
              Раньше это были 3 обычные <button> без role/aria-selected/aria-controls.
              Теперь screen reader правильно объявляет это как таб-лист с 3 табами.
              Keyboard navigation: ArrowLeft/Right, Home, End. */}
          <div style={{ marginBottom: 'var(--mac-spacing-5)' }}>
            <div
              role="tablist"
              aria-label={t('misc.lfs_metody_dvuhfaktornoy_autenti')}
              style={{ display: 'flex', gap: 'var(--mac-spacing-2)', marginBottom: 'var(--mac-spacing-4)' }}
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
                      padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                      background: isActive ? colors.primary as string[500] : 'transparent',
                      color: isActive ? 'white' : (colors.semantic as { text?: { secondary?: string } })?.text?.secondary,
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      fontSize: 'var(--mac-font-size-xs)',
                      cursor: 'pointer',
                      font: 'inherit',
                      outline: isActive ? `2px solid ${colors.primary as string[500]}` : 'none',
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
          padding: 'var(--mac-spacing-5)',
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
        padding: 'var(--mac-spacing-5)',
        position: 'relative'
      }}
    >

      <Card className="login-form-auth" style={{
        width: '100%',
      maxWidth: '400px',
      // UX Audit: card background следует за темой через --mac-* tokens.
      background: isDark
        ? 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg, #1c1c1e), transparent 16%) 0%, color-mix(in srgb, var(--mac-card-bg, var(--mac-text-primary)), transparent 26%) 100%)'
        : 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg, #ffffff), transparent 16%) 0%, color-mix(in srgb, var(--mac-card-bg, var(--mac-bg-secondary)), transparent 26%) 100%)',
        backdropFilter: 'blur(26px) saturate(140%)',
        WebkitBackdropFilter: 'blur(26px) saturate(140%)',
        border: '1px solid var(--mac-card-border, rgba(255, 255, 255, 0.42))',
        boxShadow: `
          0 18px 48px color-mix(in srgb, var(--mac-text-primary, #0f172a), transparent 82%),
          0 2px 8px color-mix(in srgb, var(--mac-text-primary, #0f172a), transparent 94%),
          inset 0 1px 0 color-mix(in srgb, var(--mac-card-bg, #fff), transparent 45%)
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
              fontSize: 'var(--mac-font-size-3xl)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              // UX Audit Stage 2 (Login issue 3.3): --mac-text-primary вместо #1d1d1f
              color: 'var(--mac-text-primary, #1d1d1f)',
              letterSpacing: '-0.5px'
            }}>
              {/* UX Audit Stage 2 (Login issue 3.5): aria-hidden на эмодзи,
                  чтобы скринридер не читал «encryption key emoji». */}
              <span aria-hidden="true">🔐</span>{' '}Вход в систему
            </span>
            <span style={{
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-normal)',
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
            {/* UX Audit: селектор «Тип входа» удалён — был функционально мёртв.
                loginType менял только label/placeholder, но API всегда получал
                поле username. Backend сам определяет тип по формату ввода.
                Теперь — единое поле «Логин» с подсказкой. */}
            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: 'var(--mac-spacing-2)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary, #1d1d1f)', fontWeight: 'var(--mac-font-weight-medium)' }}>
                Логин *
              </label>
              <Input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleInputChange}
                required
                autoComplete="username"
                placeholder={t('misc.lfs_imya_polzovatelya_email_ili_')}
                style={authControlStyles} />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: 'var(--mac-spacing-2)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary, #1d1d1f)', fontWeight: 'var(--mac-font-weight-medium)' }}>{t('misc.lfs_parol')}</label>
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
                  placeholder={t('misc.lfs_vvedite_parol')}
                  style={authControlStyles}
                  aria-describedby={capsLockOn ? 'capslock-warning' : undefined}
                />

                <Button type="button" variant="ghost" size="small" onClick={() => setShowPassword(!showPassword)} style={{ position: 'absolute', right: 4, top: 4, ...authGhostButtonStyles, ...authButtonBaseStyles }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                    {showPassword ? t('misc.lfs_skryt') : t('misc.lfs_pokazat')}
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
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    color: 'var(--mac-warning-active, var(--mac-warning))',
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
                {loading ? t('misc.lfs_vhod') : t('misc.lfs_voyti')}
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
          Стили перенесены с хардкодов (#0f172a, var(--mac-text-secondary)) на design tokens.
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
