import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { api, setToken } from '../../api/client';
import { setProfile } from '../../stores/auth';
import auth from '../../stores/auth.js';
import { getRouteForProfile } from '../../constants/routes';
import { colors } from '../../theme/tokens';
import TwoFactorVerify from '../TwoFactorVerify.jsx';
import { Button, Card, CardHeader, CardTitle, CardContent, Input, Select, Checkbox, Alert } from '../ui/macos';

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

const LoginFormStyled = ({ onLogin, onRegister, onForgotPassword }) => {
  const { theme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';
  
  const [formData, setFormData] = useState({
    username: 'admin@example.com',
    password: 'admin123',
    loginType: 'username'
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  
  // 2FA состояние
  const [requires2FA, setRequires2FA] = useState(false);
  const [pending2FAToken, setPending2FAToken] = useState('');
  const [twoFactorMethod, setTwoFactorMethod] = useState('totp');

  // Функция для проверки защищенных панелей
  const isProtectedPanelPath = (pathname) => {
    const prefixes = [
      '/admin','/registrar-panel','/doctor-panel','/lab-panel','/cashier-panel',
      '/cardiologist','/dermatologist','/dentist'
    ];
    return prefixes.some(p => pathname === p || pathname.startsWith(p + '/'));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      // Принудительно используем значения по умолчанию, если поля пустые
      const username = formData.username || 'admin@example.com';
      const password = formData.password || 'admin123';
      
      const credentials = {
        username: username,
        password: password,
        remember_me: rememberMe
      };

      console.log('🔍 Отправляемые данные:', credentials);
      console.log('📝 formData:', formData);

      // Используем основной backend на порту 8000
      const response = await fetch('http://localhost:8000/api/v1/auth/minimal-login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ошибка авторизации');
      }
      
      const data = await response.json();
      
      // Проверяем, требуется ли 2FA (в простом сервере 2FA отключено)
      if (data.requires_2fa && data.pending_2fa_token) {
        setRequires2FA(true);
        setPending2FAToken(data.pending_2fa_token);
        setLoading(false);
        return;
      }
      
      // Обычный вход без 2FA
      if (data.access_token) {
        // Сохраняем токен единообразно для всех клиентов
        setToken(data.access_token);
        localStorage.setItem('auth_token', data.access_token);
        
        try {
          // Используем данные пользователя из ответа авторизации
          setProfile(data.user);
          
          // Расширенная логика перенаправления
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

          // Детальная аналитика входа
          console.log('🔐 Login redirect:', { 
            from: fromClean, 
            computedRoute, 
            target, 
            profile: profile?.role || 'unknown',
            timestamp: new Date().toISOString()
          });
          
          navigate(target, { replace: true });
        } catch (profileError) {
          console.warn('Не удалось получить профиль:', profileError);
          navigate('/', { replace: true });
        }
      } else {
        throw new Error('Не получен токен доступа');
      }
    } catch (err) {
      // Улучшенная обработка ошибок с нормализацией
      let errorMessage = 'Ошибка входа';
      
      if (err?.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          // Pydantic validation errors
          errorMessage = detail.map(error => `${error.loc?.join('.')}: ${error.msg}`).join(', ');
        } else if (typeof detail === 'string') {
          errorMessage = detail;
        }
      } else if (err?.normalizedMessage) {
        // Используем нормализованное сообщение об ошибке
        errorMessage = err.normalizedMessage;
      } else if (err?.message) {
        errorMessage = err.message;
      }
      
      // Логирование ошибки для аналитики
      console.error('🚨 Login error:', {
        error: errorMessage,
        timestamp: new Date().toISOString(),
        username: formData.username,
        loginType: formData.loginType
      });
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handle2FASuccess = async (response) => {
    try {
      if (response.data?.access_token) {
        setToken(response.data.access_token);
        
        const profileResponse = await api.get('/auth/me');
        setProfile(profileResponse.data);
        
        await new Promise(resolve => setTimeout(resolve, 100));
        const state = auth.getState ? auth.getState() : { profile: null };
        const profile = state?.profile || null;
        const computedRoute = getRouteForProfile(profile);
        const target = computedRoute || from || '/';
        
        navigate(target, { replace: true });
      }
    } catch (err) {
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
    setFormData(prev => ({
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
                }}
              >
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
                }}
              >
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
                }}
              >
                Восстановление
              </button>
            </div>
          </div>

          <TwoFactorVerify
            method={twoFactorMethod}
            pendingToken={pending2FAToken}
            onSuccess={handle2FASuccess}
            onCancel={handle2FACancel}
          />
        </div>
      </div>
    );
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
      
      <Card style={{ 
        width: '100%', 
        maxWidth: '420px',
        // macOS-стиль карточки: полупрозрачная с размытием
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255, 255, 255, 0.2)',
        boxShadow: `
          0 8px 32px rgba(0, 0, 0, 0.1),
          0 0 0 1px rgba(255, 255, 255, 0.05),
          inset 0 1px 0 rgba(255, 255, 255, 0.1)
        `,
        borderRadius: '20px',
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
        <CardContent>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px' }}>Тип входа</label>
              <Select
                value={formData.loginType}
                onChange={(val) => setFormData(prev => ({ ...prev, loginType: val }))}
                options={[
                  { value: 'username', label: 'Имя пользователя' },
                  { value: 'email', label: 'Email' },
                  { value: 'phone', label: 'Телефон' }
                ]}
              />
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px' }}>
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
              />
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px' }}>Пароль *</label>
              <div style={{ position: 'relative' }}>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  required
                  autoComplete="current-password"
                  placeholder="Введите пароль"
                />
                <Button type="button" variant="ghost" size="small" onClick={() => setShowPassword(!showPassword)} style={{ position: 'absolute', right: 4, top: 4 }}>
                  {showPassword ? 'Скрыть' : 'Показать'}
                </Button>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Checkbox checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} /> Запомнить меня
              </label>
              <Button type="button" variant="ghost" onClick={onForgotPassword}>
                Забыли пароль?
              </Button>
            </div>

            {error && (
              <Alert variant="danger" style={{ marginBottom: 12 }}>{error}</Alert>
            )}

            <Button type="submit" variant="primary" fullWidth disabled={loading}>
              {loading ? 'Вход...' : 'ВОЙТИ →'}
            </Button>
          </form>

          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <Button type="button" variant="outline" fullWidth onClick={onRegister}>Регистрация</Button>
            <Button type="button" variant="outline" fullWidth>Гость</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default LoginFormStyled;

