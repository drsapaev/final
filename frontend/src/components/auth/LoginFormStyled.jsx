import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowRight, AtSign, Eye, EyeOff, LogIn, CircleHelp, Phone, UserPlus, UserRound } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { api, buildApiUrl, setToken } from '../../api/client';
import { setProfile } from '../../stores/auth';
import auth from '../../stores/auth.js';
import { getRouteForProfile } from '../../constants/routes';
import { getEffectiveRouteByPath } from '../../routing/routeSelectors.js';
import { colors } from '../../theme/tokens';
import TwoFactorVerify from '../TwoFactorVerify.jsx';
import ForgotPassword from './ForgotPassword';
import { formatLoginErrorMessage, LOGIN_ERROR_MESSAGES } from './loginErrorUtils';
import { Button, Card, CardHeader, CardTitle, CardContent, Input, Select, Checkbox, Alert } from '../ui/macos';
import logger from '../../utils/logger';

// macOS-стиль анимации для декоративных элементов
const floatingAnimation = `
  @keyframes float {
    0%, 100% { transform: translateY(0px) rotate(0deg); }
    50% { transform: translateY(-20px) rotate(180deg); }
  }
`;

// Добавляем стили в head
if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = floatingAnimation;
  document.head.appendChild(style);
}

const LoginFormStyled = () => {void
  useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';
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

      // 2FA-aware canonical login endpoint; keep current-origin API resolution for smoke stability.
      const response = await fetch(buildApiUrl('/authentication/login'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(credentials)
      });

      if (!response.ok) {
        const responseText = await response.text();
        let errorData = null;

        if (responseText) {
          try {
            errorData = JSON.parse(responseText);
          } catch {
            errorData = { detail: responseText };
          }
        }

        throw new Error(formatLoginErrorMessage({
          responseStatus: response.status,
          responseDetail: errorData?.detail,
          responseMessage: errorData?.message,
          fallbackMessage: 'Ошибка авторизации',
        }));
      }

      const data = await response.json();

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
          setToken(accessToken);
          localStorage.setItem('auth_token', accessToken);
          navigate('/change-password-required', {
            state: { currentPassword: formData.password },
            replace: true
          });
          return;
        }

        // Сохраняем токен единообразно для всех клиентов
        setToken(accessToken);
        localStorage.setItem('auth_token', accessToken);

        try {
          // Используем данные пользователя из ответа авторизации
          setProfile(data.user);

          // Расширенная логика перенаправления
          await new Promise((resolve) => setTimeout(resolve, 100));
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
          navigate('/', { replace: true });
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

        await new Promise((resolve) => setTimeout(resolve, 100));
        const state = auth.getState ? auth.getState() : { profile: null };
        const profile = state?.profile || null;
        const computedRoute = getRouteForProfile(profile);
        const target = computedRoute || from || '/';

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

          {/* Переключатель методов 2FA */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
              <button
                type="button"
                onClick={() => setTwoFactorMethod('totp')}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  background: twoFactorMethod === 'totp' ? colors.primary[500] : 'transparent',
                  color: twoFactorMethod === 'totp' ? 'white' : colors.semantic.text.secondary,
                  border: '1px solid #e1e5e9',
                  borderRadius: '6px',
                  fontSize: '12px',
                  cursor: 'pointer'
                }}>

                Приложение
              </button>
              <button
                type="button"
                onClick={() => setTwoFactorMethod('backup')}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  background: twoFactorMethod === 'backup' ? colors.primary[500] : 'transparent',
                  color: twoFactorMethod === 'backup' ? 'white' : colors.semantic.text.secondary,
                  border: '1px solid #e1e5e9',
                  borderRadius: '6px',
                  fontSize: '12px',
                  cursor: 'pointer'
                }}>

                Backup код
              </button>
              <button
                type="button"
                onClick={() => setTwoFactorMethod('recovery')}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  background: twoFactorMethod === 'recovery' ? colors.primary[500] : 'transparent',
                  color: twoFactorMethod === 'recovery' ? 'white' : colors.semantic.text.secondary,
                  border: '1px solid #e1e5e9',
                  borderRadius: '6px',
                  fontSize: '12px',
                  cursor: 'pointer'
                }}>

                Восстановление
              </button>
            </div>
          </div>

          <TwoFactorVerify
            method={twoFactorMethod}
            pendingToken={pending2FAToken}
            onSuccess={handle2FASuccess}
            onCancel={handle2FACancel} />

        </div>
      </div>);

  }

  // Если нажали "Забыли пароль", показываем компонент восстановления
  if (showForgotPassword) {
    return (
      <div style={{
        minHeight: '100vh',
        background: '#1d1d1f',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        position: 'relative'
      }}>
        <ForgotPassword
          onBack={() => setShowForgotPassword(false)}
          onSuccess={() => setShowForgotPassword(false)} />

      </div>);

  }

  return (
    <div style={{
      minHeight: '100vh',
      // macOS-стиль фона: темно-серый как в macOS Dark Mode
      background: '#1d1d1f',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      position: 'relative'
    }}>

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
              color: '#1d1d1f',
              letterSpacing: '-0.5px'
            }}>
              🔐 Вход в систему
            </span>
            <span style={{
              fontSize: '14px',
              fontWeight: '400',
              color: '#86868b',
              letterSpacing: '0.1px'
            }}>
              Система управления клиникой
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent style={{ paddingTop: 12, paddingBottom: 14 }}>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: '#1d1d1f', fontWeight: 500 }}>Тип входа</label>
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
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: '#1d1d1f', fontWeight: 500 }}>
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
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: '#1d1d1f', fontWeight: 500 }}>Пароль *</label>
              <div style={{ position: 'relative' }}>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  required
                  autoComplete="current-password"
                  placeholder="Введите пароль"
                  style={authControlStyles} />

                <Button type="button" variant="ghost" size="small" onClick={() => setShowPassword(!showPassword)} style={{ position: 'absolute', right: 4, top: 4, ...authGhostButtonStyles, ...authButtonBaseStyles }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                    {showPassword ? 'Скрыть' : 'Показать'}
                  </span>
                </Button>
              </div>
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

            <Button type="button" variant="primary" fullWidth disabled={loading} onClick={handleSubmit} size="large" style={{ ...authPrimaryButtonStyles, ...authButtonBaseStyles }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <LogIn size={16} />
                {loading ? 'Вход...' : 'ВОЙТИ'}
                {!loading && <ArrowRight size={16} />}
              </span>
            </Button>
          </form>

          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <Button type="button" variant="outline" fullWidth size="small" onClick={() => navigate('/register')} style={{ ...authSecondaryButtonStyles, ...authButtonBaseStyles }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <UserPlus size={16} />
                Регистрация
              </span>
            </Button>
            <Button type="button" variant="outline" fullWidth size="small" onClick={() => navigate('/')} style={{ ...authSecondaryButtonStyles, ...authButtonBaseStyles }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <UserRound size={16} />
                Гость
              </span>
            </Button>
          </div>
        </CardContent>
        <style>{`
          .login-form-auth .mac-input,
          .login-form-auth .mac-input-label,
          .login-form-auth .mac-input-hint,
          .login-form-auth .mac-input-error {
            color: #0f172a !important;
          }

          .login-form-auth .mac-input::placeholder {
            color: #64748b !important;
            opacity: 1 !important;
          }

          .login-form-auth .mac-select-trigger {
            background: rgba(255, 255, 255, 0.96) !important;
            color: #0f172a !important;
            border-color: rgba(148, 163, 184, 0.7) !important;
          }

          .login-form-auth .mac-select-trigger span,
          .login-form-auth .mac-select-trigger svg {
            color: inherit !important;
          }

          .login-form-auth .mac-select-list {
            background: rgba(255, 255, 255, 0.98) !important;
            color: #0f172a !important;
            border-color: rgba(148, 163, 184, 0.7) !important;
          }

          .login-form-auth .mac-select-item {
            color: #0f172a !important;
          }

          .login-form-auth .mac-select-item:hover {
            color: #0f172a !important;
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
            box-shadow: 0 10px 18px rgba(15, 23, 42, 0.08) !important;
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
