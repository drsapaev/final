/**
 * @deprecated Эта форма устарела и заменена на LoginFormStyled.jsx
 * Используйте LoginFormStyled.jsx для новой реализации аутентификации
 *
 * Эта форма оставлена для обратной совместимости, но не рекомендуется к использованию
 */
import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { colors } from '../../theme/tokens';
import { Button, Card, Input } from '../../design-system/components';
import { Eye, EyeOff, User, Lock, Mail, Phone, Shield } from 'lucide-react';

const LoginForm = ({ onLogin, onRegister, onForgotPassword }) => {
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

  const loginTypes = [
    { value: 'username', label: 'Имя пользователя', icon: User },
    { value: 'email', label: 'Email', icon: Mail },
    { value: 'phone', label: 'Телефон', icon: Phone }
  ];

  const handleInputChange = (field) => (event) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.value
    }));
    // Очищаем ошибки при изменении
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const credentials = {
        username: formData.username || 'admin@example.com',
        password: formData.password || 'admin123',
        remember_me: rememberMe
      };

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

      // Проверяем, требуется ли 2FA
      if (data.requires_2fa && data.pending_2fa_token) {
        setRequires2FA(true);
        setPending2FAToken(data.pending_2fa_token);
        setLoading(false);
        return;
      }

      // Обычный вход без 2FA
      if (data.access_token) {
        localStorage.setItem('auth_token', data.access_token);

        // Перенаправление
        navigate('/', { replace: true });

        if (onLogin) {
          onLogin(data);
        }
      } else {
        throw new Error('Не получен токен доступа');
      }
    } catch (err) {
      setError(err.message || 'Ошибка входа');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = () => {
    if (onRegister) {
      onRegister();
    }
  };

  const handleForgotPassword = () => {
    if (onForgotPassword) {
      onForgotPassword();
    }
  };

  const handleTwoFactor = () => {
    // Переход к двухфакторной аутентификации
    window.location.href = '/two-factor';
  };

  useEffect(() => {
    // Загружаем сохраненного пользователя
    const rememberedUser = localStorage.getItem('remembered_user');
    if (rememberedUser) {
      setFormData(prev => ({ ...prev, username: rememberedUser }));
      setRememberMe(true);
    }
  }, []);

  const getInputLabel = () => {
    switch (formData.loginType) {
      case 'email': return 'Email адрес';
      case 'phone': return 'Номер телефона';
      default: return 'Имя пользователя';
    }
  };

  const getInputType = () => {
    switch (formData.loginType) {
      case 'email': return 'email';
      case 'phone': return 'tel';
      default: return 'text';
    }
  };

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
        <Card style={{
          background: colors.semantic.background.primary,
          borderRadius: '12px',
          boxShadow: `0 20px 40px ${colors.semantic.surface.overlay}`,
          padding: '40px',
          width: '100%',
          maxWidth: '400px'
        }}>
          {/* Заголовок 2FA */}
          <div style={{ textAlign: 'center', marginBottom: '30px' }}>
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
              color: 'white'
            }}>
              <Shield size={24} />
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
              {['totp', 'backup', 'recovery'].map((method) => (
                <button
                  key={method}
                  type="button"
                  onClick={() => setTwoFactorMethod(method)}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    background: twoFactorMethod === method ? colors.primary[500] : 'transparent',
                    color: twoFactorMethod === method ? 'white' : colors.semantic.text.secondary,
                    border: `1px solid ${colors.semantic.border.medium}`,
                    borderRadius: '6px',
                    fontSize: '12px',
                    cursor: 'pointer'
                  }}
                >
                  {method === 'totp' ? 'Приложение' : method === 'backup' ? 'Backup код' : 'Восстановление'}
                </button>
              ))}
            </div>
          </div>

          {/* Здесь будет компонент TwoFactorVerify */}
          <div style={{ color: colors.status.danger, textAlign: 'center' }}>
            TwoFactorVerify component will be integrated here
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: `linear-gradient(135deg, ${colors.primary[500]} 0%, ${colors.primary[700]} 100%)`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <Card style={{
        background: colors.semantic.background.primary,
        borderRadius: '12px',
        boxShadow: `0 20px 40px ${colors.semantic.surface.overlay}`,
        padding: '40px',
        width: '100%',
        maxWidth: '400px'
      }}>
        {/* Заголовок */}
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
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
            color: 'white'
          }}>
            🏥
          </div>
          <h1 style={{
            fontSize: '24px',
            fontWeight: 'bold',
            color: colors.semantic.text.primary,
            margin: '0 0 8px 0'
          }}>
            Вход в систему
          </h1>
          <p style={{
            color: colors.semantic.text.secondary,
            margin: '0',
            fontSize: '14px'
          }}>
            Система управления клиникой
          </p>
        </div>

        {/* Сообщения об ошибках */}
        {error && (
          <div style={{
            background: colors.status.danger,
            color: 'white',
            padding: '12px',
            borderRadius: '8px',
            marginBottom: '20px',
            fontSize: '14px'
          }}>
            {error}
          </div>
        )}

        {/* Форма */}
        <form onSubmit={handleSubmit}>
          {/* Тип входа */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: colors.semantic.text.primary
            }}>
              Тип входа
            </label>
            <select
              name="loginType"
              value={formData.loginType}
              onChange={(e) => setFormData(prev => ({ ...prev, loginType: e.target.value }))}
              style={{
                width: '100%',
                padding: '12px',
                border: `2px solid ${colors.semantic.border.medium}`,
                borderRadius: '8px',
                fontSize: '14px',
                background: colors.semantic.background.primary,
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
            >
              {loginTypes.map((type) => {
                const Icon = type.icon;
                return (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Поле ввода */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: colors.semantic.text.primary
            }}>
              {formData.loginType === 'username' ? 'Имя пользователя' :
               formData.loginType === 'email' ? 'Email' : 'Телефон'} *
            </label>
            <Input
              type={formData.loginType === 'email' ? 'email' : 'text'}
              name="username"
              value={formData.username}
              onChange={(e) => setFormData(prev => ({ ...prev, username: e.target.value }))}
              required
              placeholder={`Введите ${formData.loginType === 'username' ? 'имя пользователя' :
                          formData.loginType === 'email' ? 'email' : 'телефон'}`}
              style={{
                width: '100%',
                padding: '12px',
                border: `2px solid ${colors.semantic.border.medium}`,
                borderRadius: '8px',
                fontSize: '14px',
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
            />
          </div>

          {/* Пароль */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: colors.semantic.text.primary
            }}>
              Пароль *
            </label>
            <div style={{ position: 'relative' }}>
              <Input
                type={showPassword ? 'text' : 'password'}
                name="password"
                value={formData.password}
                onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                required
                placeholder="Введите пароль"
                style={{
                  width: '100%',
                  padding: '12px 40px 12px 12px',
                  border: `2px solid ${colors.semantic.border.medium}`,
                  borderRadius: '8px',
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'border-color 0.2s'
                }}
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
                  color: colors.semantic.text.secondary
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Запомнить меня */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            marginBottom: '20px'
          }}>
            <input
              type="checkbox"
              id="rememberMe"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              style={{ marginRight: '8px' }}
            />
            <label htmlFor="rememberMe" style={{
              fontSize: '14px',
              color: colors.semantic.text.secondary
            }}>
              Запомнить меня
            </label>
          </div>

          {/* Кнопка входа */}
          <Button
            type="submit"
            variant="primary"
            disabled={loading}
            style={{
              width: '100%',
              padding: '12px',
              fontSize: '16px',
              marginBottom: '20px'
            }}
          >
            {loading ? 'Вход...' : 'Войти'}
          </Button>

          {/* Ссылки */}
          <div style={{ textAlign: 'center' }}>
            <button
              type="button"
              onClick={onForgotPassword}
              style={{
                background: 'none',
                border: 'none',
                color: colors.primary[500],
                cursor: 'pointer',
                fontSize: '14px',
                marginRight: '16px'
              }}
            >
              Забыли пароль?
            </button>
            <button
              type="button"
              onClick={onRegister}
              style={{
                background: 'none',
                border: 'none',
                color: colors.primary[500],
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              Регистрация
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
};

/**
 * ⚠️ ВНИМАНИЕ: Эта форма устарела!
 *
 * Используйте LoginFormStyled.jsx вместо этой формы.
 * LoginForm.jsx оставлена только для обратной совместимости.
 *
 * Новая форма LoginFormStyled.jsx:
 * - Использует консолидированную цветовую систему
 * - Поддерживает все современные функции аутентификации
 * - Соответствует дизайну-системе проекта
 */
export default LoginForm;

