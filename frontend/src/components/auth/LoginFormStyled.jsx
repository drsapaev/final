import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { api, setToken } from '../../api/client';
import { setProfile } from '../../stores/auth';
import auth from '../../stores/auth.js';
import { getRouteForProfile } from '../../constants/routes';
import TwoFactorVerify from '../TwoFactorVerify.jsx';

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
          
          // Перенаправление
          await new Promise(resolve => setTimeout(resolve, 100));
          const state = auth.getState ? auth.getState() : { profile: null };
          const profile = state?.profile || null;
          const computedRoute = getRouteForProfile(profile);
          const target = computedRoute || from || '/';
          
          navigate(target, { replace: true });
        } catch (profileError) {
          console.warn('Не удалось получить профиль:', profileError);
          navigate('/', { replace: true });
        }
      } else {
        throw new Error('Не получен токен доступа');
      }
    } catch (err) {
      let errorMessage = 'Ошибка входа';
      
      if (err?.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          // Pydantic validation errors
          errorMessage = detail.map(error => `${error.loc?.join('.')}: ${error.msg}`).join(', ');
        } else if (typeof detail === 'string') {
          errorMessage = detail;
        }
      } else if (err?.message) {
        errorMessage = err.message;
      }
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
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
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
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
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
              color: '#333',
              margin: '0 0 8px 0'
            }}>
              Двухфакторная аутентификация
            </h1>
            <p style={{
              color: '#666',
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
                  background: twoFactorMethod === 'totp' ? '#667eea' : 'transparent',
                  color: twoFactorMethod === 'totp' ? 'white' : '#666',
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
                  background: twoFactorMethod === 'backup' ? '#667eea' : 'transparent',
                  color: twoFactorMethod === 'backup' ? 'white' : '#666',
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
                  background: twoFactorMethod === 'recovery' ? '#667eea' : 'transparent',
                  color: twoFactorMethod === 'recovery' ? 'white' : '#666',
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
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
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
        {/* Заголовок */}
        <div style={{
          textAlign: 'center',
          marginBottom: '30px'
        }}>
          <div style={{
            width: '60px',
            height: '60px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
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
            <span style={{ position: 'relative', zIndex: 1 }}>🏥</span>
          </div>
          <h1 style={{
            fontSize: '24px',
            fontWeight: 'bold',
            color: '#333',
            margin: '0 0 8px 0'
          }}>
            Вход в систему
          </h1>
          <p style={{
            color: '#666',
            margin: '0',
            fontSize: '14px'
          }}>
            Система управления клиникой
          </p>
        </div>

        {/* Форма */}
        <form onSubmit={handleSubmit}>
          {/* Тип входа */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: '#333'
            }}>
              Тип входа
            </label>
            <select
              name="loginType"
              value={formData.loginType}
              onChange={handleInputChange}
              style={{
                width: '100%',
                padding: '12px',
                border: '2px solid #e1e5e9',
                borderRadius: '8px',
                fontSize: '14px',
                background: 'white',
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
            >
              <option value="username">Имя пользователя</option>
              <option value="email">Email</option>
              <option value="phone">Телефон</option>
            </select>
          </div>

          {/* Имя пользователя */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: '#333'
            }}>
              {formData.loginType === 'username' ? 'Имя пользователя' : 
               formData.loginType === 'email' ? 'Email' : 'Телефон'} *
            </label>
            <input
              type={formData.loginType === 'email' ? 'email' : 'text'}
              name="username"
              value={formData.username}
              onChange={handleInputChange}
              required
              autoComplete={formData.loginType === 'email' ? 'email' : 'username'}
              style={{
                width: '100%',
                padding: '12px',
                border: '2px solid #e1e5e9',
                borderRadius: '8px',
                fontSize: '14px',
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
              placeholder={`Введите ${formData.loginType === 'username' ? 'имя пользователя' : 
                          formData.loginType === 'email' ? 'email' : 'телефон'}`}
            />
          </div>

          {/* Пароль */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: '#333'
            }}>
              Пароль *
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                required
                autoComplete="current-password"
                style={{
                  width: '100%',
                  padding: '12px 40px 12px 12px',
                  border: '2px solid #e1e5e9',
                  borderRadius: '8px',
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'border-color 0.2s'
                }}
                placeholder="Введите пароль"
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
                  color: '#666',
                  fontSize: '18px'
                }}
              >
                {showPassword ? '👁️' : '👁️‍🗨️'}
              </button>
            </div>
          </div>

          {/* Запомнить меня и забыли пароль */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '30px'
          }}>
            <label style={{
              display: 'flex',
              alignItems: 'center',
              cursor: 'pointer',
              fontSize: '14px',
              color: '#333'
            }}>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                style={{ marginRight: '8px' }}
              />
              Запомнить меня
            </label>
            <button
              type="button"
              onClick={onForgotPassword}
              style={{
                background: 'none',
                border: 'none',
                color: '#667eea',
                cursor: 'pointer',
                fontSize: '14px',
                textDecoration: 'underline'
              }}
            >
              Забыли пароль?
            </button>
          </div>

          {/* Ошибка */}
          {error && (
            <div style={{
              background: '#fee',
              color: '#c33',
              padding: '12px',
              borderRadius: '8px',
              marginBottom: '20px',
              fontSize: '14px',
              textAlign: 'center'
            }}>
              {error}
            </div>
          )}

          {/* Кнопка входа */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '14px',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '16px',
              fontWeight: 'bold',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              transition: 'opacity 0.2s',
              textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)'
            }}
          >
            {loading ? 'Вход...' : 'ВОЙТИ →'}
          </button>
        </form>

        {/* Разделитель */}
        <div style={{
          margin: '30px 0',
          textAlign: 'center',
          position: 'relative'
        }}>
          <div style={{
            height: '1px',
            background: '#e1e5e9',
            position: 'relative'
          }}>
            <span style={{
              background: 'white',
              padding: '0 20px',
              color: '#666',
              fontSize: '14px',
              position: 'absolute',
              top: '-10px',
              left: '50%',
              transform: 'translateX(-50%)'
            }}>
              или
            </span>
          </div>
        </div>

        {/* Кнопки регистрации */}
        <div style={{
          display: 'flex',
          gap: '10px'
        }}>
          <button
            type="button"
            onClick={onRegister}
            style={{
              flex: 1,
              padding: '12px',
              background: 'white',
              border: '2px solid #e1e5e9',
              borderRadius: '8px',
              fontSize: '14px',
              cursor: 'pointer',
              transition: 'border-color 0.2s'
            }}
          >
            Регистрация
          </button>
          <button
            type="button"
            style={{
              flex: 1,
              padding: '12px',
              background: 'white',
              border: '2px solid #e1e5e9',
              borderRadius: '8px',
              fontSize: '14px',
              cursor: 'pointer',
              transition: 'border-color 0.2s'
            }}
          >
            Гость
          </button>
        </div>
      </div>
    </div>
  );
};

export default LoginFormStyled;

